function(context is Context, queries)
{
    var id = ["bossTest"] as Id;

    // 基體 100 x 100 x 20 mm
    fCuboid(context, id + "base", {
            "corner1" : vector(0, 0, 0) * millimeter,
            "corner2" : vector(100, 100, 20) * millimeter
    });

    // 找出法線為 +Z 的頂面
    var topFaces = [];
    for (var f in evaluateQuery(context, qCreatedBy(id + "base", EntityType.FACE)))
    {
        var tp = evFaceTangentPlane(context, { "face" : f, "parameter" : vector(0.5, 0.5) });
        if (tolerantEquals(tp.normal, vector(0, 0, 1)))
            topFaces = append(topFaces, f);
    }

    // smartBoss 的核心邏輯（直徑 20mm、高 15mm、不加圓角）
    var toolBodies = [];
    var i = 0;
    for (var face in topFaces)
    {
        var fid = id + unstableIdComponent(i);
        var tp = evFaceTangentPlane(context, { "face" : face, "parameter" : vector(0.5, 0.5) });
        var sk = newSketchOnPlane(context, fid + "sketch", { "sketchPlane" : tp });
        skCircle(sk, "circle", { "center" : vector(0, 0) * millimeter,
                                 "radius" : 10 * millimeter });
        skSolve(sk);
        opExtrude(context, fid + "extrude", {
                "entities" : qSketchRegion(fid + "sketch"),
                "direction" : tp.normal,
                "endBound" : BoundingType.BLIND,
                "endDepth" : 15 * millimeter
        });
        toolBodies = append(toolBodies, qCreatedBy(fid + "extrude", EntityType.BODY));
        i += 1;
    }

    opBoolean(context, id + "boolean", {
            "tools" : qUnion(toolBodies),
            "targets" : qCreatedBy(id + "base", EntityType.BODY),
            "operationType" : BooleanOperationType.UNION
    });

    // 量測
    var bodies = evaluateQuery(context, qAllSolidBodies());
    var vol = evVolume(context, { "entities" : qAllSolidBodies() });
    var nFaces = size(evaluateQuery(context, qOwnedByBody(qAllSolidBodies(), EntityType.FACE)));

    return {
        "選到頂面數" : size(topFaces),
        "body數" : size(bodies),
        "體積mm3" : vol / (millimeter ^ 3),
        "面數" : nFaces
    };
}
