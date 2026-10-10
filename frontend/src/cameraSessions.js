const KEY='pause-camera-sessions-v2';
export function readCameraSessions() {
  const parsed=JSON.parse(localStorage.getItem(KEY)||'[]');
  if(!Array.isArray(parsed)) throw new Error('Saved session data is invalid.');
  return parsed;
}
export function saveCameraSession(session) {
  const rows=readCameraSessions();
  if(rows.some(r=>r.id===session.id)) return;
  localStorage.setItem(KEY,JSON.stringify([session,...rows]));
}
export function deleteCameraSession(id) {
  localStorage.setItem(KEY,JSON.stringify(readCameraSessions().filter(r=>r.id!==id)));
}
