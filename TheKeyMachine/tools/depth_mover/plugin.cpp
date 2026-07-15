#include <algorithm>
#include <cmath>
#include <iomanip>
#include <memory>
#include <sstream>
#include <vector>

#include <maya/M3dView.h>
#include <maya/MArgList.h>
#include <maya/MDagPath.h>
#include <maya/MCursor.h>
#include <maya/MEvent.h>
#include <maya/MFnPlugin.h>
#include <maya/MFnTransform.h>
#include <maya/MGlobal.h>
#include <maya/MItSelectionList.h>
#include <maya/MFrameContext.h>
#include <maya/MUIDrawManager.h>
#include <maya/MPxCommand.h>
#include <maya/MPxContext.h>
#include <maya/MPxContextCommand.h>
#include <maya/MSelectionList.h>
#include <maya/MVector.h>

#if defined(_WIN32)
#define TKM_PLUGIN_EXPORT __declspec(dllexport)
#else
#define TKM_PLUGIN_EXPORT __attribute__((visibility("default")))
#endif

namespace {

const char* kContextCommand = "tkmDepthMoverNativeContextCmd";
const char* kBuildCommand = "tkmDepthMoverNativeBuild";
const char* kConfigureCommand = "tkmDepthMoverNativeConfigure";
const char* kBuildId = "2026_07_15_native_cpp_9";
constexpr double kDistancePerPixel = 0.07;
constexpr double kSensitivityPixelsPerDoubling = 160.0;
constexpr double kMinimumSensitivity = 0.125;
constexpr double kMaximumSensitivity = 4.0;
constexpr double kMinimumCameraProximitySensitivity = 0.1;
MString gToolIcon;

struct Target {
    MDagPath path;
    MVector initialTranslation;
    MVector direction;
    MVector finalTranslation;
    double initialCameraDistance;
    double currentDistance;
};

class BuildCommand : public MPxCommand {
public:
    static void* creator() { return new BuildCommand(); }
    MStatus doIt(const MArgList&) override {
        setResult(kBuildId);
        return MS::kSuccess;
    }
};

class ConfigureCommand : public MPxCommand {
public:
    static void* creator() { return new ConfigureCommand(); }
    MStatus doIt(const MArgList& args) override {
        if (args.length() != 1) {
            MGlobal::displayError(
                "tkmDepthMoverNativeConfigure requires a tool image path.");
            return MS::kInvalidParameter;
        }
        MStatus status;
        gToolIcon = args.asString(0, &status);
        return status;
    }
};

class DepthDrag {
public:
    void captureSelection() {
        targets_.clear();

        M3dView view = M3dView::active3dView();
        MDagPath cameraPath;
        MStatus status = view.getCamera(cameraPath);
        if (!status) return;
        if (cameraPath.hasFn(MFn::kCamera)) cameraPath.pop();

        MFnTransform camera(cameraPath, &status);
        if (!status) return;
        const MVector cameraPosition =
            MVector(camera.rotatePivot(MSpace::kWorld, &status));
        if (!status) return;

        MSelectionList selection;
        MGlobal::getActiveSelectionList(selection);
        MItSelectionList iterator(selection, MFn::kTransform);
        for (; !iterator.isDone(); iterator.next()) {
            MDagPath path;
            iterator.getDagPath(path);
            if (path == cameraPath) continue;
            MFnTransform transform(path, &status);
            if (!status) continue;

            const MVector translation = transform.getTranslation(MSpace::kWorld, &status);
            if (!status) continue;
            const MPoint pivot = transform.rotatePivot(MSpace::kWorld, &status);
            if (!status) continue;

            MVector direction = MVector(pivot) - cameraPosition;
            const double cameraDistance = direction.length();
            if (cameraDistance < 1.0e-9) continue;
            direction.normalize();
            targets_.push_back({
                path,
                translation,
                direction,
                translation,
                cameraDistance,
                0.0,
            });
        }
    }

    bool empty() const { return targets_.empty(); }

    void advanceDistance(double distanceDelta) {
        for (Target& target : targets_) {
            const double signedCameraDistance =
                target.initialCameraDistance + target.currentDistance;
            const double distanceRatio = std::max(
                0.0,
                std::min(
                    1.0,
                    signedCameraDistance / target.initialCameraDistance));
            const double proximitySensitivity =
                kMinimumCameraProximitySensitivity +
                ((1.0 - kMinimumCameraProximitySensitivity) * distanceRatio);
            const double adjustedDelta = distanceDelta * proximitySensitivity;
            target.currentDistance += adjustedDelta;
            target.finalTranslation =
                target.initialTranslation +
                target.direction * target.currentDistance;
        }
    }

    MStatus applyFinal() { return apply(false); }
    MStatus cancel() { return apply(true); }

    MStatus commit() {
        // Live API edits are intentionally not added to Maya's undo queue.
        // Restore the press state, then commit final values with Maya-native
        // xform commands in one chunk so the plug-in itself remains unloadable.
        MStatus result = apply(true);
        MStatus status = MGlobal::executeCommand(
            "undoInfo -openChunk -chunkName \"TKM Depth Mover\"",
            false,
            false);
        if (!status) return status;

        for (const Target& target : targets_) {
            std::ostringstream command;
            command << std::setprecision(17)
                    << "xform -worldSpace -translation "
                    << target.finalTranslation.x << ' '
                    << target.finalTranslation.y << ' '
                    << target.finalTranslation.z << " \""
                    << target.path.fullPathName().asChar() << "\"";
            status = MGlobal::executeCommand(
                MString(command.str().c_str()), false, true);
            if (!status && result) result = status;
        }

        status = MGlobal::executeCommand(
            "undoInfo -closeChunk", false, false);
        if (!status && result) result = status;
        M3dView::active3dView().refresh(false, true);
        return result;
    }

private:
    MStatus apply(bool initial) {
        MStatus result = MS::kSuccess;
        for (const Target& target : targets_) {
            MStatus status;
            MFnTransform transform(target.path, &status);
            if (status) {
                status = transform.setTranslation(
                    initial ? target.initialTranslation : target.finalTranslation,
                    MSpace::kWorld);
            }
            if (!status && result) result = status;
        }
        M3dView::active3dView().refresh(false, true);
        return result;
    }

    std::vector<Target> targets_;
};

class DepthContext : public MPxContext {
public:
    DepthContext() {
        setTitleString("Depth Mover");
        setHelpString(
            "Drag vertically for depth; move left or right to adjust sensitivity.");
        if (gToolIcon.length() > 0) setImage(gToolIcon, MPxContext::kImage1);
    }

    void toolOnSetup(MEvent&) override { setCursor(MCursor::handCursor); }

    void toolOffCleanup() override {
        if (command_) command_->cancel();
        command_.reset();
        setCursor(MCursor::defaultCursor);
        MPxContext::toolOffCleanup();
    }

    MStatus doPress(MEvent& event) override {
        if (event.mouseButton() != MEvent::kLeftMouse) return MS::kNotImplemented;
        event.getPosition(anchorX_, anchorY_);
        previousY_ = anchorY_;
        command_ = std::make_unique<DepthDrag>();
        command_->captureSelection();
        if (command_->empty()) {
            MGlobal::displayWarning(
                "Depth Mover needs a movable transform and an active camera.");
            command_.reset();
            return MS::kFailure;
        }
        dragged_ = false;
        setCursor(MCursor::handCursor);
        return MS::kSuccess;
    }

    MStatus doPress(
            MEvent& event,
            MHWRender::MUIDrawManager&,
            const MHWRender::MFrameContext&) override {
        return doPress(event);
    }

    MStatus doDrag(MEvent& event) override {
        if (command_ == nullptr) return MS::kFailure;
        short x = 0;
        short y = 0;
        event.getPosition(x, y);
        const double horizontalOffset = static_cast<double>(x - anchorX_);
        const double rawSensitivity = std::pow(
            2.0, horizontalOffset / kSensitivityPixelsPerDoubling);
        const double sensitivity = std::max(
            kMinimumSensitivity,
            std::min(kMaximumSensitivity, rawSensitivity));
        double modifierSensitivity = 1.0;
        if (event.isModifierControl()) modifierSensitivity *= 0.3;
        if (event.isModifierShift()) modifierSensitivity *= 3.0;
        const short verticalDelta = y - previousY_;
        previousY_ = y;
        if (verticalDelta == 0) return MS::kSuccess;
        command_->advanceDistance(
            static_cast<double>(verticalDelta) *
            kDistancePerPixel * sensitivity * modifierSensitivity);
        dragged_ = true;
        return command_->applyFinal();
    }

    MStatus doDrag(
            MEvent& event,
            MHWRender::MUIDrawManager&,
            const MHWRender::MFrameContext&) override {
        return doDrag(event);
    }

    MStatus doRelease(MEvent& event) override {
        if (command_ == nullptr) return MS::kFailure;
        MStatus status = doDrag(event);
        if (status && dragged_) {
            status = command_->commit();
        } else {
            command_->cancel();
        }
        command_.reset();
        return status;
    }

    MStatus doRelease(
            MEvent& event,
            MHWRender::MUIDrawManager&,
            const MHWRender::MFrameContext&) override {
        return doRelease(event);
    }

private:
    std::unique_ptr<DepthDrag> command_;
    short anchorX_ = 0;
    short anchorY_ = 0;
    short previousY_ = 0;
    bool dragged_ = false;
};

class DepthContextCommand : public MPxContextCommand {
public:
    static void* creator() { return new DepthContextCommand(); }
    MPxContext* makeObj() override { return new DepthContext(); }
};

}  // namespace

TKM_PLUGIN_EXPORT
MStatus initializePlugin(MObject pluginObject) {
    MFnPlugin plugin(pluginObject, "TheKeyMachine", "1.0", "Any");
    MStatus status = plugin.registerCommand(
        kConfigureCommand, ConfigureCommand::creator);
    if (!status) return status;
    status = plugin.registerCommand(kBuildCommand, BuildCommand::creator);
    if (!status) {
        plugin.deregisterCommand(kConfigureCommand);
        return status;
    }
    status = plugin.registerContextCommand(
        kContextCommand, DepthContextCommand::creator);
    if (!status) {
        plugin.deregisterCommand(kBuildCommand);
        plugin.deregisterCommand(kConfigureCommand);
    }
    return status;
}

TKM_PLUGIN_EXPORT
MStatus uninitializePlugin(MObject pluginObject) {
    MFnPlugin plugin(pluginObject);
    MStatus contextStatus = plugin.deregisterContextCommand(kContextCommand);
    MStatus buildStatus = plugin.deregisterCommand(kBuildCommand);
    MStatus configureStatus = plugin.deregisterCommand(kConfigureCommand);
    if (!contextStatus) return contextStatus;
    return buildStatus ? configureStatus : buildStatus;
}
