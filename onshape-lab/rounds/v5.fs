FeatureScript 3070;
import(path : "onshape/std/geometry.fs", version : "3070.0");

annotation { "Feature Type Name" : "Smart Boss" }
export const smartBoss = defineFeature(function(context is Context, id is Id, definition is map)
    precondition
    {
        annotation { "Name" : "Faces", "Filter" : EntityType.FACE && GeometryType.PLANE }
        definition.faces is Query;

        annotation { "Name" : "Boss Diameter" }
        isLength(definition.bossDiameter, LENGTH_BOUNDS);

        annotation { "Name" : "Boss Height" }
        isLength(definition.bossHeight, LENGTH_BOUNDS);

        annotation { "Name" : "Add Fillet" }
        definition.addFillet is boolean;

        if (definition.addFillet)
        {
            annotation { "Name" : "Fillet Radius" }
            isLength(definition.filletRadius, LENGTH_BOUNDS);
        }
    }
    {
        var faces = evaluateQuery(context, definition.faces);
        var toolBodies = [];
        var i = 0;

        for (var face in faces)
        {
            var faceId = id + unstableIdComponent(i);

            // evBox3d 在 geometry.fs 下編譯不過（實測 2026-08-29），
            // 改用 evFaceTangentPlane 直接取得面上一點與外法線。
            var tp = evFaceTangentPlane(context, {
                    "face" : face,
                    "parameter" : vector(0.5, 0.5)
            });

            var sketchId = faceId + "sketch";
            // tp 是 Plane 值，必須用 newSketchOnPlane；newSketch 收的是平面 Query。
            var sk = newSketchOnPlane(context, sketchId, { "sketchPlane" : tp });
            skCircle(sk, "circle", {
                    "center" : vector(0, 0) * millimeter,
                    "radius" : definition.bossDiameter / 2
            });
            skSolve(sk);

            var extrudeId = faceId + "extrude";
            opExtrude(context, extrudeId, {
                    "entities" : qSketchRegion(sketchId),
                    "direction" : tp.normal,
                    "endBound" : BoundingType.BLIND,
                    "endDepth" : definition.bossHeight
            });

            toolBodies = append(toolBodies, qCreatedBy(extrudeId, EntityType.BODY));
            i += 1;
        }

        if (size(toolBodies) > 0)
        {
            var booleanId = id + "boolean";
            // UNION 時「所有」待合併實體都要放進 tools；給了 targets 會得到
            // BOOLEAN_BAD_INPUT（targets 只用於 SUBTRACTION / INTERSECTION）。實測 2026-08-29。
            opBoolean(context, booleanId, {
                    "tools" : qUnion(append(toolBodies, qOwnerBody(definition.faces))),
                    "operationType" : BooleanOperationType.UNION
            });

            if (definition.addFillet)
            {
                var filletEdges = qEntityFilter(qCreatedBy(booleanId), EntityType.EDGE);
                if (!isQueryEmpty(context, filletEdges))
                {
                    opFillet(context, id + "fillet", {
                            "entities" : filletEdges,
                            "radius" : definition.filletRadius
                    });
                }
            }
        }
    });
