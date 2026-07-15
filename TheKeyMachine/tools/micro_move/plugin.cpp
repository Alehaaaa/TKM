#include <algorithm>
#include <chrono>
#include <cmath>
#include <memory>
#include <string>
#include <vector>

#include <CoreFoundation/CoreFoundation.h>
#include <CoreGraphics/CoreGraphics.h>
#include <ImageIO/ImageIO.h>

#include <maya/MArgList.h>
#include <maya/MDagPath.h>
#include <maya/MCursor.h>
#include <maya/MEvent.h>
#include <maya/MEulerRotation.h>
#include <maya/MFnDagNode.h>
#include <maya/MFnDependencyNode.h>
#include <maya/MFnFreePointTriadManip.h>
#include <maya/MFnMatrixData.h>
#include <maya/MFnNumericData.h>
#include <maya/MFnPlugin.h>
#include <maya/MFnRotateManip.h>
#include <maya/MFnTransform.h>
#include <maya/MGlobal.h>
#include <maya/MItSelectionList.h>
#include <maya/MManipData.h>
#include <maya/MMatrix.h>
#include <maya/MObject.h>
#include <maya/MPxCommand.h>
#include <maya/MPxContextCommand.h>
#include <maya/MPxManipContainer.h>
#include <maya/MPxSelectionContext.h>
#include <maya/MQuaternion.h>
#include <maya/MSelectionList.h>
#include <maya/MTransformationMatrix.h>
#include <maya/MVector.h>

namespace {

const char* kMoveManipName = "tkmMicroMoveManip";
const char* kRotateManipName = "tkmMicroRotateManip";
const char* kMoveContextCommand = "tkmMicroMoveContextCmd";
const char* kRotateContextCommand = "tkmMicroRotateContextCmd";
const char* kBuildCommand = "tkmMicroMoveBuild";
const char* kConfigureCommand = "tkmMicroMoveConfigure";
const char* kRefreshCommand = "tkmMicroMoveRefresh";
const char* kBuildId = "2026_07_15_native_cpp_13";

// Manipulator node IDs must remain stable. Before public third-party
// distribution, replace these only with IDs assigned to TKM by Autodesk.
const MTypeId kMoveManipId(0x0013B2A0);
const MTypeId kRotateManipId(0x0013B2A1);

constexpr double kMinGain = 1.0 / 6.0;
constexpr double kMaxGain = 1.0;
constexpr double kAccelerationStart = 120.0;
constexpr double kAccelerationFull = 1400.0;

constexpr short kCursorSize = 32;
constexpr short kCursorHotspot = 3;

struct CursorAsset {
    std::vector<unsigned char> bits;
    std::vector<unsigned char> mask;
    std::unique_ptr<MCursor> cursor;
};

CursorAsset gOpenCursor;
CursorAsset gPinchedCursor;
MString gToolIcon;
double gCursorGain = kMinGain;
short gPreviousCursorX = 0;
short gPreviousCursorY = 0;
std::chrono::steady_clock::time_point gPreviousCursorTime;

bool loadCursorImage(
        const MString& path,
        CursorAsset& asset,
        MString& error) {
    const std::string pathString = path.asChar();
    CFURLRef url = CFURLCreateFromFileSystemRepresentation(
        nullptr,
        reinterpret_cast<const UInt8*>(pathString.c_str()),
        pathString.size(),
        false);
    if (url == nullptr) {
        error = "Could not create a URL for cursor image: ";
        error += pathString.c_str();
        return false;
    }

    CGImageSourceRef source = CGImageSourceCreateWithURL(url, nullptr);
    CFRelease(url);
    if (source == nullptr) {
        error = "Could not read cursor image: ";
        error += pathString.c_str();
        return false;
    }

    CGImageRef image = CGImageSourceCreateImageAtIndex(source, 0, nullptr);
    CFRelease(source);
    if (image == nullptr) {
        error = "Could not decode cursor image: ";
        error += pathString.c_str();
        return false;
    }

    constexpr size_t channels = 4;
    const size_t rgbaRowBytes = kCursorSize * channels;
    std::vector<unsigned char> rgba(rgbaRowBytes * kCursorSize, 0);
    CGColorSpaceRef colorSpace = CGColorSpaceCreateDeviceRGB();
    CGContextRef context = CGBitmapContextCreate(
        rgba.data(),
        kCursorSize,
        kCursorSize,
        8,
        rgbaRowBytes,
        colorSpace,
        kCGImageAlphaPremultipliedLast | kCGBitmapByteOrder32Big);
    CGColorSpaceRelease(colorSpace);
    if (context == nullptr) {
        CGImageRelease(image);
        error = "Could not allocate the Micro Move cursor bitmap.";
        return false;
    }

    CGContextSetInterpolationQuality(context, kCGInterpolationHigh);
    CGContextDrawImage(
        context,
        CGRectMake(0.0, 0.0, kCursorSize, kCursorSize),
        image);
    CGContextRelease(context);
    CGImageRelease(image);

    const size_t monoRowBytes = (kCursorSize + 7) / 8;
    asset.bits.assign(monoRowBytes * kCursorSize, 0);
    asset.mask.assign(monoRowBytes * kCursorSize, 0);
    for (size_t y = 0; y < kCursorSize; ++y) {
        for (size_t x = 0; x < kCursorSize; ++x) {
            const size_t pixel = (y * rgbaRowBytes) + (x * channels);
            const unsigned char red = rgba[pixel];
            const unsigned char green = rgba[pixel + 1];
            const unsigned char blue = rgba[pixel + 2];
            const unsigned char alpha = rgba[pixel + 3];
            if (alpha < 16) continue;

            const size_t monoByte = (y * monoRowBytes) + (x / 8);
            const unsigned char monoBit =
                static_cast<unsigned char>(1u << (x % 8));
            asset.mask[monoByte] |= monoBit;
            const unsigned int luminance =
                (299u * red + 587u * green + 114u * blue) / 1000u;
            if (luminance < 128u) asset.bits[monoByte] |= monoBit;
        }
    }

    asset.cursor = std::make_unique<MCursor>(
        kCursorSize,
        kCursorSize,
        kCursorHotspot,
        kCursorHotspot,
        asset.bits.data(),
        asset.mask.data());
    return true;
}

void beginCursorSample(const MEvent& event) {
    event.getPosition(gPreviousCursorX, gPreviousCursorY);
    gPreviousCursorTime = std::chrono::steady_clock::now();
    gCursorGain = kMinGain;
}

void updateCursorGain(const MEvent& event) {
    short x = 0;
    short y = 0;
    event.getPosition(x, y);
    const auto now = std::chrono::steady_clock::now();
    const double elapsed = std::max(
        std::chrono::duration<double>(now - gPreviousCursorTime).count(),
        0.001);
    const double distance = std::hypot(
        static_cast<double>(x - gPreviousCursorX),
        static_cast<double>(y - gPreviousCursorY));
    const double speed = distance / elapsed;
    double amount = (speed - kAccelerationStart) /
        (kAccelerationFull - kAccelerationStart);
    amount = std::max(0.0, std::min(1.0, amount));
    amount = amount * amount * (3.0 - 2.0 * amount);
    gCursorGain = kMinGain + (kMaxGain - kMinGain) * amount;
    gPreviousCursorX = x;
    gPreviousCursorY = y;
    gPreviousCursorTime = now;
}

double keyboardModifierGain() {
    const CGEventFlags flags = CGEventSourceFlagsState(
        kCGEventSourceStateCombinedSessionState);
    double gain = 1.0;
    if ((flags & kCGEventFlagMaskControl) != 0) gain *= 0.3;
    if ((flags & kCGEventFlagMaskShift) != 0) gain *= 3.0;
    return gain;
}

MVector plugVector(const MPlug& plug) {
    return MVector(
        plug.child(0).asDouble(),
        plug.child(1).asDouble(),
        plug.child(2).asDouble());
}

MManipData vectorData(const MVector& value) {
    MFnNumericData data;
    MObject object = data.create(MFnNumericData::k3Double);
    data.setData(value.x, value.y, value.z);
    return MManipData(object);
}

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
        if (args.length() != 3) {
            MGlobal::displayError(
                "tkmMicroMoveConfigure requires open, pinched, and tool image paths.");
            return MS::kInvalidParameter;
        }

        MStatus status;
        const MString openPath = args.asString(0, &status);
        if (!status) return status;
        const MString pinchedPath = args.asString(1, &status);
        if (!status) return status;
        const MString toolIcon = args.asString(2, &status);
        if (!status) return status;

        CursorAsset openCursor;
        CursorAsset pinchedCursor;
        MString error;
        if (!loadCursorImage(openPath, openCursor, error) ||
                !loadCursorImage(pinchedPath, pinchedCursor, error)) {
            MGlobal::displayError(error);
            return MS::kFailure;
        }
        gOpenCursor = std::move(openCursor);
        gPinchedCursor = std::move(pinchedCursor);
        gToolIcon = toolIcon;
        return MS::kSuccess;
    }
};

class MicroMoveManip : public MPxManipContainer {
public:
    static void* creator() { return new MicroMoveManip(); }
    static MStatus initialize() { return MPxManipContainer::initialize(); }

    MStatus createChildren() override {
        moveManipPath_ = addFreePointTriadManip("tkmMicroMoveHandle", "Micro Move");
        MFnFreePointTriadManip move(moveManipPath_);
        pointIndex_ = move.pointIndex();
        return MS::kSuccess;
    }

    MStatus connectToDependNode(const MObject& node) override {
        MStatus status;
        MFnDependencyNode nodeFn(node, &status);
        if (!status) return status;
        targetPlug_ = nodeFn.findPlug("translate", false, &status);
        if (!status) return status;

        targetPlugIndex_ = addManipToPlugConversionCallback(
            targetPlug_,
            static_cast<manipToPlugConversionCallback>(
                &MicroMoveManip::translationChanged));

        MFnDagNode dagFn(node, &status);
        if (!status) return status;
        status = dagFn.getPath(nodePath_);
        if (!status) return status;

        MMatrix worldMatrix = nodePath_.inclusiveMatrix();
        worldOrientation_ = MTransformationMatrix(worldMatrix).rotation();
        MMatrix parentMatrix;
        parentMatrix.setToIdentity();
        if (nodePath_.length() > 1) {
            MDagPath parentPath(nodePath_);
            parentPath.pop();
            parentMatrix = parentPath.inclusiveMatrix();
        }

        MMatrix offsetParentMatrix;
        offsetParentMatrix.setToIdentity();
        MPlug offsetParentPlug = nodeFn.findPlug(
            "offsetParentMatrix", false, &status);
        if (status) {
            MObject matrixData = offsetParentPlug.asMObject(&status);
            if (status && !matrixData.isNull()) {
                MFnMatrixData matrixFn(matrixData, &status);
                if (status) offsetParentMatrix = matrixFn.matrix(&status);
            }
        }
        if (!status) return status;
        channelToWorld_ = offsetParentMatrix * parentMatrix;
        worldToChannel_ = channelToWorld_.inverse();

        MFnTransform transform(nodePath_, &status);
        if (!status) return status;
        MPoint pivot = transform.rotatePivot(MSpace::kWorld, &status);
        if (!status) return status;

        initialPivotWorld_ = pivot;
        initialTranslate_ = plugVector(targetPlug_);
        outputTranslate_ = plugVector(targetPlug_);
        previousPoint_ = MPoint::origin;

        MFnFreePointTriadManip move(moveManipPath_, &status);
        if (!status) return status;
        move.setPoint(MPoint::origin);
        move.setTranslation(MVector(pivot), MSpace::kWorld);
        move.setRotation(worldOrientation_, MSpace::kWorld);
        move.setDrawArrowHead(true);

        status = finishAddingManips();
        if (!status) return status;
        return MPxManipContainer::connectToDependNode(node);
    }

    MStatus doPress() override {
        dragging_ = true;
        MStatus status;
        MFnTransform transform(nodePath_, &status);
        if (status) {
            initialPivotWorld_ = transform.rotatePivot(MSpace::kWorld, &status);
        }
        initialTranslate_ = plugVector(targetPlug_);
        outputTranslate_ = plugVector(targetPlug_);
        if (!getConverterManipValue(pointIndex_, previousPoint_)) {
            previousPoint_ = MPoint::origin;
        }
        return MPxManipContainer::doPress();
    }

    MStatus doDrag() override { return MPxManipContainer::doDrag(); }

    MStatus doRelease() override {
        MStatus status = MPxManipContainer::doRelease();
        dragging_ = false;
        return status;
    }

private:
    MManipData translationChanged(unsigned int index) {
        if (index != targetPlugIndex_ || !dragging_) {
            return vectorData(outputTranslate_);
        }
        MPoint current;
        if (!getConverterManipValue(pointIndex_, current)) {
            return vectorData(outputTranslate_);
        }
        MVector localDelta = current - previousPoint_;
        previousPoint_ = current;
        MVector worldDelta = localDelta.rotateBy(worldOrientation_);
        MVector channelDelta = worldDelta * worldToChannel_;
        outputTranslate_ +=
            channelDelta * gCursorGain * keyboardModifierGain();

        // The child manipulator follows the cursor at full speed. Offset its
        // DAG transform so the visible handle instead stays on the scaled
        // object pivot returned by this converter.
        MVector outputChannelDelta = outputTranslate_ - initialTranslate_;
        MVector outputWorldDelta = outputChannelDelta * channelToWorld_;
        MPoint desiredPivot = initialPivotWorld_ + outputWorldDelta;
        MVector rawWorldOffset = MVector(current).rotateBy(worldOrientation_);
        MFnFreePointTriadManip move(moveManipPath_);
        move.setTranslation(
            MVector(desiredPivot) - rawWorldOffset,
            MSpace::kWorld);
        return vectorData(outputTranslate_);
    }

    MDagPath moveManipPath_;
    MDagPath nodePath_;
    MPlug targetPlug_;
    unsigned int pointIndex_ = 0;
    unsigned int targetPlugIndex_ = 0;
    MMatrix worldToChannel_;
    MMatrix channelToWorld_;
    MQuaternion worldOrientation_;
    MPoint initialPivotWorld_;
    MPoint previousPoint_;
    MVector initialTranslate_;
    MVector outputTranslate_;
    bool dragging_ = false;
};

class MicroRotateManip : public MPxManipContainer {
public:
    static void* creator() { return new MicroRotateManip(); }
    static MStatus initialize() { return MPxManipContainer::initialize(); }

    MStatus createChildren() override {
        rotateManipPath_ = addRotateManip("tkmMicroRotateHandle", "Micro Rotate");
        MFnRotateManip rotate(rotateManipPath_);
        rotationIndex_ = rotate.rotationIndex();
        return MS::kSuccess;
    }

    MStatus connectToDependNode(const MObject& node) override {
        MStatus status;
        MFnDependencyNode nodeFn(node, &status);
        if (!status) return status;
        targetPlug_ = nodeFn.findPlug("rotate", false, &status);
        if (!status) return status;
        MPlug pivotPlug = nodeFn.findPlug("rotatePivot", false, &status);
        if (!status) return status;
        int orderValue = nodeFn.findPlug("rotateOrder", false, &status).asInt();
        if (!status) return status;
        rotationOrder_ = static_cast<MEulerRotation::RotationOrder>(orderValue);
        targetNode_ = node;

        targetPlugIndex_ = addManipToPlugConversionCallback(
            targetPlug_,
            static_cast<manipToPlugConversionCallback>(
                &MicroRotateManip::rotationChanged));

        MEulerRotation initial(plugVector(targetPlug_), rotationOrder_);
        outputEuler_ = initial;
        outputRotation_ = initial.asQuaternion();
        previousRawRotation_ = outputRotation_;

        MFnRotateManip rotate(rotateManipPath_, &status);
        if (!status) return status;
        rotate.setInitialRotation(initial);
        rotate.setRotateMode(MFnRotateManip::kObjectSpace);
        rotate.displayWithNode(node);
        rotate.connectToRotationCenterPlug(pivotPlug);

        status = finishAddingManips();
        if (!status) return status;
        return MPxManipContainer::connectToDependNode(node);
    }

    MStatus doPress() override {
        dragging_ = true;
        MEulerRotation initial(plugVector(targetPlug_), rotationOrder_);
        outputEuler_ = initial;
        outputRotation_ = initial.asQuaternion();
        MEulerRotation raw;
        previousRawRotation_ = getConverterManipValue(rotationIndex_, raw)
            ? raw.asQuaternion()
            : outputRotation_;
        return MPxManipContainer::doPress();
    }

    MStatus doDrag() override { return MPxManipContainer::doDrag(); }

    MStatus doRelease() override {
        MStatus status = MPxManipContainer::doRelease();
        dragging_ = false;
        MFnRotateManip rotate(rotateManipPath_);
        rotate.setInitialRotation(outputEuler_);
        rotate.setRotateMode(MFnRotateManip::kObjectSpace);
        rotate.displayWithNode(targetNode_);
        return status;
    }

private:
    MManipData rotationChanged(unsigned int index) {
        if (index == targetPlugIndex_ && dragging_) {
            MEulerRotation raw;
            if (getConverterManipValue(rotationIndex_, raw)) {
                MQuaternion current = raw.asQuaternion();
                MQuaternion rawDelta = previousRawRotation_.inverse() * current;
                MQuaternion scaledDelta = slerp(
                    MQuaternion::identity,
                    rawDelta,
                    gCursorGain * keyboardModifierGain());
                outputRotation_ *= scaledDelta;
                previousRawRotation_ = current;
            }
        }
        MEulerRotation output = outputRotation_.asEulerRotation();
        output.reorderIt(rotationOrder_);
        outputEuler_ = output.closestSolution(outputEuler_);
        return vectorData(MVector(
            outputEuler_.x, outputEuler_.y, outputEuler_.z));
    }

    MDagPath rotateManipPath_;
    MObject targetNode_;
    MPlug targetPlug_;
    unsigned int rotationIndex_ = 0;
    unsigned int targetPlugIndex_ = 0;
    MEulerRotation::RotationOrder rotationOrder_ = MEulerRotation::kXYZ;
    MEulerRotation outputEuler_;
    MQuaternion previousRawRotation_;
    MQuaternion outputRotation_;
    bool dragging_ = false;
};

class MicroSelectionContext : public MPxSelectionContext {
public:
    explicit MicroSelectionContext(const char* manipulatorName, const char* title)
        : manipulatorName_(manipulatorName) {
        setTitleString(title);
        setHelpString("Select controls or drag the Micro Move manipulator.");
        if (gToolIcon.length() > 0) setImage(gToolIcon, MPxContext::kImage1);
    }

    ~MicroSelectionContext() override {
        if (activeContext_ == this) activeContext_ = nullptr;
    }

    static void refreshActive() {
        if (activeContext_ != nullptr) rebuild(activeContext_);
    }

    void toolOnSetup(MEvent&) override {
        activeContext_ = this;
        setAllowPreSelectHilight();
        setCursor(
            gOpenCursor.cursor
                ? *gOpenCursor.cursor
                : MCursor::defaultCursor);
        rebuild(this);
    }

    void toolOffCleanup() override {
        deleteManipulators();
        if (activeContext_ == this) activeContext_ = nullptr;
        setCursor(MCursor::defaultCursor);
        MPxSelectionContext::toolOffCleanup();
    }

    MStatus doPress(MEvent& event) override {
        beginCursorSample(event);
        setCursor(
            gPinchedCursor.cursor
                ? *gPinchedCursor.cursor
                : MCursor::defaultCursor);
        return MPxSelectionContext::doPress(event);
    }

    MStatus doDrag(MEvent& event) override {
        updateCursorGain(event);
        return MPxSelectionContext::doDrag(event);
    }

    MStatus doRelease(MEvent& event) override {
        MStatus status = MPxSelectionContext::doRelease(event);
        setCursor(
            gOpenCursor.cursor
                ? *gOpenCursor.cursor
                : MCursor::defaultCursor);
        return status;
    }

private:
    static void rebuild(void* data) {
        auto* context = static_cast<MicroSelectionContext*>(data);
        context->deleteManipulators();
        MSelectionList selection;
        MGlobal::getActiveSelectionList(selection);
        MItSelectionList iterator(selection, MFn::kTransform);
        for (; !iterator.isDone(); iterator.next()) {
            MObject node;
            iterator.getDependNode(node);
            if (node.isNull()) continue;
            MObject manipObject;
            MStatus status;
            MPxManipContainer* manipulator = MPxManipContainer::newManipulator(
                context->manipulatorName_, manipObject, &status);
            if (!status || manipulator == nullptr) continue;
            status = context->addManipulator(manipObject);
            if (!status) {
                MGlobal::displayWarning(
                    "Micro Move could not add a manipulator for a selected node.");
                continue;
            }
            status = manipulator->connectToDependNode(node);
            if (!status) {
                MGlobal::displayWarning(
                    "Micro Move could not connect to a selected transform.");
            }
        }
    }

    MString manipulatorName_;
    static MicroSelectionContext* activeContext_;
};

MicroSelectionContext* MicroSelectionContext::activeContext_ = nullptr;

class RefreshCommand : public MPxCommand {
public:
    static void* creator() { return new RefreshCommand(); }
    MStatus doIt(const MArgList&) override {
        MicroSelectionContext::refreshActive();
        return MS::kSuccess;
    }
};

class MoveContextCommand : public MPxContextCommand {
public:
    static void* creator() { return new MoveContextCommand(); }
    MPxContext* makeObj() override {
        return new MicroSelectionContext(kMoveManipName, "Micro Move");
    }
};

class RotateContextCommand : public MPxContextCommand {
public:
    static void* creator() { return new RotateContextCommand(); }
    MPxContext* makeObj() override {
        return new MicroSelectionContext(kRotateManipName, "Micro Rotate");
    }
};

}  // namespace

__attribute__((visibility("default")))
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

    status = plugin.registerCommand(kRefreshCommand, RefreshCommand::creator);
    if (!status) {
        plugin.deregisterCommand(kBuildCommand);
        plugin.deregisterCommand(kConfigureCommand);
        return status;
    }

    status = plugin.registerNode(
        kMoveManipName, kMoveManipId, MicroMoveManip::creator,
        MicroMoveManip::initialize, MPxNode::kManipContainer);
    if (!status) {
        plugin.deregisterCommand(kRefreshCommand);
        plugin.deregisterCommand(kBuildCommand);
        plugin.deregisterCommand(kConfigureCommand);
        return status;
    }

    status = plugin.registerNode(
        kRotateManipName, kRotateManipId, MicroRotateManip::creator,
        MicroRotateManip::initialize, MPxNode::kManipContainer);
    if (!status) {
        plugin.deregisterNode(kMoveManipId);
        plugin.deregisterCommand(kRefreshCommand);
        plugin.deregisterCommand(kBuildCommand);
        plugin.deregisterCommand(kConfigureCommand);
        return status;
    }

    status = plugin.registerContextCommand(kMoveContextCommand, MoveContextCommand::creator);
    if (!status) {
        plugin.deregisterNode(kRotateManipId);
        plugin.deregisterNode(kMoveManipId);
        plugin.deregisterCommand(kRefreshCommand);
        plugin.deregisterCommand(kBuildCommand);
        plugin.deregisterCommand(kConfigureCommand);
        return status;
    }

    status = plugin.registerContextCommand(
        kRotateContextCommand, RotateContextCommand::creator);
    if (!status) {
        plugin.deregisterContextCommand(kMoveContextCommand);
        plugin.deregisterNode(kRotateManipId);
        plugin.deregisterNode(kMoveManipId);
        plugin.deregisterCommand(kRefreshCommand);
        plugin.deregisterCommand(kBuildCommand);
        plugin.deregisterCommand(kConfigureCommand);
    }
    return status;
}

__attribute__((visibility("default")))
MStatus uninitializePlugin(MObject pluginObject) {
    MFnPlugin plugin(pluginObject);
    MStatus result = MS::kSuccess;
    auto captureFailure = [&result](const MStatus& status) {
        if (result && !status) result = status;
    };
    captureFailure(plugin.deregisterContextCommand(kRotateContextCommand));
    captureFailure(plugin.deregisterContextCommand(kMoveContextCommand));
    captureFailure(plugin.deregisterNode(kRotateManipId));
    captureFailure(plugin.deregisterNode(kMoveManipId));
    captureFailure(plugin.deregisterCommand(kRefreshCommand));
    captureFailure(plugin.deregisterCommand(kBuildCommand));
    captureFailure(plugin.deregisterCommand(kConfigureCommand));
    gOpenCursor = CursorAsset();
    gPinchedCursor = CursorAsset();
    return result;
}
