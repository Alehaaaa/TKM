#include <maya/MDagPath.h>
#include <maya/MEulerRotation.h>
#include <maya/MFnDagNode.h>
#include <maya/MFnDependencyNode.h>
#include <maya/MFnFreePointTriadManip.h>
#include <maya/MFnNumericData.h>
#include <maya/MFnPlugin.h>
#include <maya/MFnRotateManip.h>
#include <maya/MFnTransform.h>
#include <maya/MGlobal.h>
#include <maya/MItSelectionList.h>
#include <maya/MManipData.h>
#include <maya/MMatrix.h>
#include <maya/MMessage.h>
#include <maya/MModelMessage.h>
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
const char* kBuildId = "2026_07_15_native_cpp_1";

const MTypeId kMoveManipId(0x0013B2A0);
const MTypeId kRotateManipId(0x0013B2A1);

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

void callRuntime(const char* expression) {
    MGlobal::executePythonCommand(MString(expression), false, false);
}

double cursorGain() {
    double gain = 1.0 / 6.0;
MStatus status = MGlobal::executePythonCommand(
        "__import__('TheKeyMachine.tools.micro_move.api', "
        "fromlist=['api']).manipulator_drag_gain()",
        gain,
        false,
        false);
    if (!status || gain < 0.0 || gain > 1.0) {
        return 1.0 / 6.0;
    }
    return gain;
}

class BuildCommand : public MPxCommand {
public:
    static void* creator() { return new BuildCommand(); }
    MStatus doIt(const MArgList&) override {
        setResult(kBuildId);
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
        parentInverse_.setToIdentity();
        if (nodePath_.length() > 1) {
            MDagPath parentPath(nodePath_);
            parentPath.pop();
            parentInverse_ = parentPath.inclusiveMatrixInverse();
        }

        MFnTransform transform(nodePath_, &status);
        if (!status) return status;
        MPoint pivot = transform.rotatePivot(MSpace::kWorld, &status);
        if (!status) return status;

        outputTranslate_ = plugVector(targetPlug_);
        previousPoint_ = MPoint::origin;

        MFnFreePointTriadManip move(moveManipPath_, &status);
        if (!status) return status;
        move.setPoint(MPoint::origin);
        move.setTranslation(MVector(pivot), MSpace::kWorld);
        move.setRotation(worldOrientation_, MSpace::kWorld);
        move.setDrawArrowHead(true);

        finishAddingManips();
        return MPxManipContainer::connectToDependNode(node);
    }

    MStatus doPress() override {
        dragging_ = true;
        outputTranslate_ = plugVector(targetPlug_);
        if (!getConverterManipValue(pointIndex_, previousPoint_)) {
            previousPoint_ = MPoint::origin;
        }
        callRuntime(
            "__import__('TheKeyMachine.tools.micro_move.api', "
            "fromlist=['api']).begin_manipulator_drag()");
        return MPxManipContainer::doPress();
    }

    MStatus doDrag() override { return MPxManipContainer::doDrag(); }

    MStatus doRelease() override {
        MStatus status = MPxManipContainer::doRelease();
        dragging_ = false;
        callRuntime(
            "__import__('TheKeyMachine.tools.micro_move.api', "
            "fromlist=['api']).end_manipulator_drag()");
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
        MVector parentDelta = worldDelta * parentInverse_;
        outputTranslate_ += parentDelta * cursorGain();
        return vectorData(outputTranslate_);
    }

    MDagPath moveManipPath_;
    MDagPath nodePath_;
    MPlug targetPlug_;
    unsigned int pointIndex_ = 0;
    unsigned int targetPlugIndex_ = 0;
    MMatrix parentInverse_;
    MQuaternion worldOrientation_;
    MPoint previousPoint_;
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

        targetPlugIndex_ = addManipToPlugConversionCallback(
            targetPlug_,
            static_cast<manipToPlugConversionCallback>(
                &MicroRotateManip::rotationChanged));

        MEulerRotation initial(plugVector(targetPlug_), rotationOrder_);
        outputRotation_ = initial.asQuaternion();
        previousRawRotation_ = outputRotation_;

        MFnRotateManip rotate(rotateManipPath_, &status);
        if (!status) return status;
        rotate.setInitialRotation(initial);
        rotate.setRotateMode(MFnRotateManip::kObjectSpace);
        rotate.displayWithNode(node);
        rotate.connectToRotationCenterPlug(pivotPlug);

        finishAddingManips();
        return MPxManipContainer::connectToDependNode(node);
    }

    MStatus doPress() override {
        dragging_ = true;
        MEulerRotation initial(plugVector(targetPlug_), rotationOrder_);
        outputRotation_ = initial.asQuaternion();
        MEulerRotation raw;
        previousRawRotation_ = getConverterManipValue(rotationIndex_, raw)
            ? raw.asQuaternion()
            : outputRotation_;
        callRuntime(
            "__import__('TheKeyMachine.tools.micro_move.api', "
            "fromlist=['api']).begin_manipulator_drag()");
        return MPxManipContainer::doPress();
    }

    MStatus doDrag() override { return MPxManipContainer::doDrag(); }

    MStatus doRelease() override {
        MStatus status = MPxManipContainer::doRelease();
        dragging_ = false;
        callRuntime(
            "__import__('TheKeyMachine.tools.micro_move.api', "
            "fromlist=['api']).end_manipulator_drag()");
        return status;
    }

private:
    MManipData rotationChanged(unsigned int index) {
        if (index == targetPlugIndex_ && dragging_) {
            MEulerRotation raw;
            if (getConverterManipValue(rotationIndex_, raw)) {
                MQuaternion current = raw.asQuaternion();
                MQuaternion rawDelta = previousRawRotation_.inverse() * current;
                MQuaternion scaledDelta = slerp(MQuaternion::identity, rawDelta, cursorGain());
                outputRotation_ *= scaledDelta;
                previousRawRotation_ = current;
            }
        }
        MEulerRotation output = outputRotation_.asEulerRotation();
        output.reorderIt(rotationOrder_);
        return vectorData(MVector(output.x, output.y, output.z));
    }

    MDagPath rotateManipPath_;
    MPlug targetPlug_;
    unsigned int rotationIndex_ = 0;
    unsigned int targetPlugIndex_ = 0;
    MEulerRotation::RotationOrder rotationOrder_ = MEulerRotation::kXYZ;
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
    }

    void toolOnSetup(MEvent&) override {
        setAllowPreSelectHilight();
        rebuild(this);
        selectionCallback_ = MModelMessage::addCallback(
            MModelMessage::kActiveListModified, rebuild, this);
    }

    void toolOffCleanup() override {
        deleteManipulators();
        if (selectionCallback_ != 0) {
            MMessage::removeCallback(selectionCallback_);
            selectionCallback_ = 0;
        }
        callRuntime(
            "__import__('TheKeyMachine.tools.micro_move.api', "
            "fromlist=['api']).end_manipulator_drag(False)");
        MPxSelectionContext::toolOffCleanup();
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
            context->addManipulator(manipObject);
            manipulator->connectToDependNode(node);
        }
    }

    MString manipulatorName_;
    MCallbackId selectionCallback_ = 0;
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
    MStatus status = plugin.registerCommand(kBuildCommand, BuildCommand::creator);
    if (!status) return status;
    status = plugin.registerNode(
        kMoveManipName, kMoveManipId, MicroMoveManip::creator,
        MicroMoveManip::initialize, MPxNode::kManipContainer);
    if (!status) return status;
    status = plugin.registerNode(
        kRotateManipName, kRotateManipId, MicroRotateManip::creator,
        MicroRotateManip::initialize, MPxNode::kManipContainer);
    if (!status) return status;
    status = plugin.registerContextCommand(kMoveContextCommand, MoveContextCommand::creator);
    if (!status) return status;
    return plugin.registerContextCommand(kRotateContextCommand, RotateContextCommand::creator);
}

__attribute__((visibility("default")))
MStatus uninitializePlugin(MObject pluginObject) {
    MFnPlugin plugin(pluginObject);
    plugin.deregisterContextCommand(kRotateContextCommand);
    plugin.deregisterContextCommand(kMoveContextCommand);
    plugin.deregisterNode(kRotateManipId);
    plugin.deregisterNode(kMoveManipId);
    return plugin.deregisterCommand(kBuildCommand);
}
