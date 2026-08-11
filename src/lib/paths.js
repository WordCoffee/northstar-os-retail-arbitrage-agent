import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
export const projectRoot = path.resolve(__dirname, '../..');

export const paths = {
  data: path.join(projectRoot, 'data'),
  snapshots: path.join(projectRoot, 'data/snapshots'),
  normalized: path.join(projectRoot, 'data/normalized'),
  scored: path.join(projectRoot, 'data/scored'),
  logs: path.join(projectRoot, 'logs'),
};
