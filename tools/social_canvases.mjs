// Emit the documented social canvases from presets.js (no duplication in Python).
import { ALL_FORMATS } from '../northstar-os-ui/src/studio/engine/presets.js';

const ids = ['ig-post', 'meta-story', 'x-post', 'linkedin', 'yt-thumb'];
const rows = ids.map((id) => {
  const f = ALL_FORMATS.find((x) => x.id === id);
  if (!f) throw new Error(`missing format ${id}`);
  return { format: id, width: f.w, height: f.h, channel: f.channel, source: f.source };
});
process.stdout.write(JSON.stringify(rows, null, 2));
