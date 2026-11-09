// 固定 JSON 桥接；所有游戏请求按收到的顺序串行执行。
let ready;
async function initialize() {
  const response = await fetch('/runtime.json', { cache: 'no-cache' });
  if (!response.ok) throw new Error('无法读取运行配置');
  const config = await response.json();
  const { loadPyodide } = await import(`${config.pyodide}pyodide.mjs`);
  const python = await loadPyodide({ indexURL: config.pyodide });
  const archive = await fetch(config.package);
  if (!archive.ok) throw new Error('无法读取故事文件');
  python.unpackArchive(await archive.arrayBuffer(), 'zip', { extractDir: '/game' });
  python.runPython('import sys, os\nsys.path.insert(0, "/game")\nos.chdir("/game")\nfrom web.runtime.bridge import call');
  return python;
}
let queue = Promise.resolve();
self.onmessage = ({ data }) => {
  queue = queue.then(async () => {
    try {
      ready ??= initialize().catch((error) => { ready = null; throw error; });
      const python = await ready;
      python.globals.set('_request_json', JSON.stringify(data.request));
      const result = JSON.parse(python.runPython('call(_request_json)'));
      python.globals.delete('_request_json');
      self.postMessage({ id: data.id, result });
    } catch (error) {
      self.postMessage({ id: data.id, error: String(error.message || error) });
    }
  });
};
