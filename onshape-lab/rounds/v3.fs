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
        
        annotation { "Name" : "Fillet Radius" }
        isLength(definition.filletRadius, LENGTH_BOUNDS);
    }
    {
        var faces = evaluateQuery(context, definition.faces);
        var i = 0;
        var toolBodies = [];
        
        for (var face in faces)
        {
            var faceId = id + unstableIdComponent(i);
            
            var plane = evPlane(context, { "face" : face });
            var box = evBox3d(context, { "topology" : face });
            var center3d = (box.minCorner + box.maxCorner) / 2;
            
            var dist = dot(center3d - plane.origin, plane.normal);
            plane.origin = center3d - plane.normal * dist;
            
            var sketchId = faceId + "sketch";
            var sk = newSketch(context, sketchId, {
                "sketchPlane" : plane
            });
            
            skCircle(sk, "circle", {
                "center" : vector(0, 0) * millimeter,
                "radius" : definition.bossDiameter / 2
            });
            skSolve(sk);
            
            var extrudeId = faceId + "extrude";
            opExtrude(context, extrudeId, {
                "entities" : qSketchRegion(sketchId),
                "direction" : plane.normal,
                "endBound" : BoundingType.BLIND,
                "endDepth" : definition.bossHeight
            });
            
            toolBodies = append(toolBodies, qCreatedBy(extrudeId, EntityType.BODY));
            i += 1;
        }
        
        if (size(toolBodies) > 0)
        {
            var booleanId = id + "boolean";
            opBoolean(context, booleanId, {
                "tools" : qUnion(toolBodies),
                "targets" : qOwnerBody(definition.faces),
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
