/** ZRS 可直接复用的消息客户端；UI 不接触 Python 对象。 */
export class GameClient {
  constructor() {
    this.nextId = 0;
    this.pending = new Map();
    this.worker = new Worker('/worker.js', { type: 'module' });
    this.worker.onmessage = ({ data }) => {
      const task = this.pending.get(data.id);
      if (!task) return;
      this.pending.delete(data.id);
      clearTimeout(task.timer);
      if (data.error) task.reject(new Error(data.error));
      else task.resolve(data.result);
    };
    this.worker.onerror = () => this.close(new Error('游戏运行环境启动失败，请重试。'));
  }
  call(request) {
    if (this.closed) return Promise.reject(new Error('游戏连接已关闭，请返回书架重新打开故事。'));
    return new Promise((resolve, reject) => {
      const id = ++this.nextId;
      const timer = setTimeout(() => this.close(new Error('加载超时，请检查网络后重试。')), 90_000);
      this.pending.set(id, { resolve, reject, timer });
      this.worker.postMessage({ id, request: { ...request, protocol_version: 1 } });
    });
  }
  close(error = new Error('会话已关闭')) {
    this.closed = true;
    this.worker.terminate();
    for (const task of this.pending.values()) {
      clearTimeout(task.timer);
      task.reject(error);
    }
    this.pending.clear();
  }
}
