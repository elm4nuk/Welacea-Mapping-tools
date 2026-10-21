import type { Annotation, Schema } from '../../api/client';
import type { Finding } from './model';
export function toFinding(a: Annotation, logicalId = a.id): Finding {
  return { id: logicalId, photoKey: a.photo_id, kind: a.kind === 'check' ? 'inspect' : a.kind,
    point: a.bbox ? { x: a.bbox[0], y: a.bbox[1] } : { x: a.x, y: a.y },
    box: a.bbox ? { x: a.bbox[0], y: a.bbox[1], width: a.bbox[2], height: a.bbox[3] } : undefined,
    source: a.source, review: a.review_status, note: a.note, confidence: a.confidence ?? undefined,
    analysisRunId: a.analysis_run_id ?? undefined, modelLabel: a.model_label ?? undefined };
}
export function annotationBody(f: Finding): Schema['AnnotationUpdate'] {
  return { kind: f.kind === 'inspect' ? 'check' : f.kind, note: f.note,
    review_status: f.review, geometry_type: f.box ? 'bbox' : 'point',
    ...(f.box ? {} : { x: f.point.x, y: f.point.y }),
    bbox: f.box ? [f.box.x, f.box.y, f.box.width, f.box.height] : null };
}
export function createBody(f: Finding): Schema['AnnotationCreate'] {
  const body = annotationBody(f);
  return { kind: f.kind === 'inspect' ? 'check' : f.kind,
    geometry_type: f.box ? 'bbox' : 'point', x: body.x, y: body.y, bbox: body.bbox,
    note: f.note, review_status: f.review === 'pending' ? 'pending' : 'accepted' };
}
