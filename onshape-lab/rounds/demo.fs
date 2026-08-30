FeatureScript 3070;
import(path : "onshape/std/geometry.fs", version : "3070.0");

annotation { "Feature Type Name" : "Smart Boss Demo" }
export const smartBossDemo = defineFeature(function(context is Context, id is Id, definition is map)
    // 透過 API 加入特徵時 parameters 為空陣列，definition 不會有任何鍵，
    // 自訂的 LengthBoundSpec 預設值只在 UI 建立特徵時生效。
    // 因此示範用特徵不宣告參數，尺寸直接寫死。
    precondition
    {
    }
    {
        // 自給自足的示範：先造基體，再對頂面施作 smartBoss 的核心邏輯，
        // 讓模型不需要使用者互動就能持久化，便於截圖與獨立量測。
        fCuboid(context, id + "base", {
                "corner1" : vector(0, 0, 0) * millimeter,
                "corner2" : vector(100, 100, 20) * millimeter
        });

        var topFaces = [];
        for (var f in evaluateQuery(context, qCreatedBy(id + "base", EntityType.FACE)))
        {
            var tp = evFaceTangentPlane(context, { "face" : f, "parameter" : vector(0.5, 0.5) });
            if (tolerantEquals(tp.normal, vector(0, 0, 1)))
                topFaces = append(topFaces, f);
        }

        var i = 0;
        for (var face in topFaces)
        {
            var fid = id + unstableIdComponent(i);
            var tp = evFaceTangentPlane(context, { "face" : face, "parameter" : vector(0.5, 0.5) });
            var sk = newSketchOnPlane(context, fid + "sketch", { "sketchPlane" : tp });
            skCircle(sk, "circle", {
                    "center" : vector(0, 0) * millimeter,
                    "radius" : 10 * millimeter });
            skSolve(sk);
            opExtrude(context, fid + "extrude", {
                    "entities" : qSketchRegion(fid + "sketch"),
                    "direction" : tp.normal,
                    "endBound" : BoundingType.BLIND,
                    "endDepth" : 15 * millimeter });
            i += 1;
        }

        // UNION：全部放 tools，不給 targets（給了會 BOOLEAN_BAD_INPUT）
        opBoolean(context, id + "boolean", {
                "tools" : qAllSolidBodies(),
                "operationType" : BooleanOperationType.UNION });

        var junction = qEntityFilter(qCreatedBy(id + "boolean"), EntityType.EDGE);
        if (!isQueryEmpty(context, junction))
        {
            opFillet(context, id + "fillet", {
                    "entities" : junction,
                    "radius" : 3 * millimeter });
        }
    });
