/**
 * 网页会话适配层。负责人：ZRS。
 *
 * 生产环境把请求交给 ZC 的运行时客户端（Pyodide Worker）；开发与浏览器
 * 测试可以换成内置的测试替身，页面渲染代码完全相同。所有请求串行执行，
 * 每次请求带会话标识与代号；切换故事后旧代号的结果直接丢弃。
 */
import { GameClient } from '../runtime/client.js';

export const FIXTURE_STORY = {
  id: 'ui_demo',
  title: '界面测试剧本',
  genre: '测试替身',
};

/** 与 tests/ui_fakes.py 的 FakeGameSession 同构：捡钥匙 → 开门 → 结局。 */
export class FixtureSession {
  constructor(storyId = FIXTURE_STORY.id) {
    this.storyId = storyId;
    this.step = 0;
    this.revision = 0;
    this.started = false;
  }

  start() {
    this.started = true;
    return { view: this.snapshot(), messages: [], error_code: null };
  }

  snapshot() {
    const ended = this.step === 2;
    const view = {
      story_id: this.storyId,
      story_title: FIXTURE_STORY.title,
      scene_id: ended ? 'exit' : 'hall',
      scene_title: ended ? '门外' : '门厅',
      text: ended ? '你走出了房间。' : '门边有一把钥匙。',
      revision: this.revision,
      turn: this.step,
      protocol_version: 1,
      choices: [],
      actions: [],
      inventory: this.step >= 1 ? [{ id: 'key', label: '钥匙', description: '一把铜钥匙。' }] : [],
      clues: [{ id: 'note', label: '门边便条', description: '钥匙可以开门。' }],
      resources: [{ id: 'oxygen', label: '氧气', value: 8 - this.step, maximum: 8 }],
      assets: {},
      ended,
      ending_id: ended ? 'out' : null,
      ending_title: ended ? '出门' : null,
    };
    if (this.step === 0) view.choices = [{ id: 'choice:take', label: '捡起钥匙', parameters: [], enabled: true, disabled_reason: '' }];
    if (this.step === 1) {
      view.choices = [{ id: 'choice:open', label: '打开房门', parameters: [], enabled: true, disabled_reason: '' }];
      view.actions = [{
        id: 'puzzle:use', label: '使用物品', enabled: true, disabled_reason: '',
        parameters: [{ key: 'item', label: '物品', kind: 'select', required: true,
          options: [{ id: 'key', label: '钥匙', description: '' }] }],
      }, {
        // 四参数动作：和真实剧本的指认一样宽，用来验证窄屏不溢出。
        id: 'mystery:accuse', label: '作出指认', enabled: true, disabled_reason: '',
        parameters: [
          { key: 'suspect', label: '指认对象', kind: 'select', required: true,
            options: [{ id: 'gu', label: '顾先生' }, { id: 'zhou', label: '周文' }] },
          { key: 'motive', label: '动机', kind: 'select', required: true,
            options: [{ id: 'debt', label: '欠债' }, { id: 'embezzle', label: '挪用账款被发现' }] },
          { key: 'means', label: '手段', kind: 'select', required: true,
            options: [{ id: 'poison', label: '下毒' }, { id: 'weight', label: '用铜镇纸击打后脑' }] },
          { key: 'evidence', label: '关键证据', kind: 'select', required: true,
            options: ['水缸里的镇纸', '周文的失言', '阿芸的实话', '地板下的暗账'].map(
              (label, i) => ({ id: `clue${i}`, label })) },
        ],
      }];
    }
    return view;
  }

  dispatch(actionId, expectedRevision, values) {
    const view = this.snapshot();
    if (expectedRevision !== this.revision) {
      return { view, messages: ['画面已更新，请重新选择。'], error_code: 'stale_revision' };
    }
    const allowed = [...view.choices, ...view.actions].filter((a) => a.enabled).map((a) => a.id);
    if (!allowed.includes(actionId)) {
      return { view, messages: ['当前不能执行这个操作。'], error_code: 'invalid_action' };
    }
    const expected = {
      'puzzle:use': { item: 'key' },
      // 四参数指认：只校验键与候选范围，用来验证表单提交链路。
      'mystery:accuse': { suspect: ['gu', 'zhou'], motive: ['debt', 'embezzle'],
        means: ['poison', 'weight'], evidence: ['clue0', 'clue1', 'clue2', 'clue3'] },
    }[actionId] ?? {};
    const valid = Object.entries(expected).every(([key, want]) => (
      Array.isArray(want) ? want.includes(values[key]) : values[key] === want))
      && Object.keys(values).length === Object.keys(expected).length;
    if (actionId === 'puzzle:use' ? JSON.stringify(values) !== JSON.stringify(expected) : !valid) {
      return { view, messages: ['请选择有效的操作参数。'], error_code: 'invalid_parameters' };
    }
    this.step += 1;
    this.revision += 1;
    return { view: this.snapshot(), messages: ['操作完成。'], error_code: null };
  }

  exportSave() {
    return { fixture: 'ui_demo', step: this.step };
  }

  restore(payload) {
    const view = this.snapshot();
    if (!payload || payload.fixture !== 'ui_demo' || ![0, 1, 2].includes(payload.step)) {
      return { view, messages: ['测试存档无效。'], error_code: 'invalid_save' };
    }
    this.step = payload.step;
    this.revision += 1;
    return { view: this.snapshot(), messages: ['已恢复测试进度。'], error_code: null };
  }
}

/** 把 Worker 客户端包装成 start / action / restore / export 四种调用。 */
export class RemoteSession {
  constructor(runtime) {
    this.runtime = runtime;
    this.client = new GameClient();
    this.sessionId = crypto.randomUUID();
  }

  async call(request) {
    return this.client.call({ ...request, session_id: this.sessionId });
  }

  async start(storyId) {
    return this.call({ method: 'start', story_id: storyId });
  }

  async dispatch(actionId, expectedRevision, values) {
    return this.call({ method: 'action', action: { action_id: actionId, expected_revision: expectedRevision, values } });
  }

  async restore(payload) {
    return this.call({ method: 'restore', payload });
  }

  async exportSave() {
    return this.call({ method: 'export' });
  }

  close() {
    this.client.close();
  }
}

/** 浏览器测试用：开启替身后页面不加载 Pyodide，也不访问网络。 */
export function fixtureRequested() {
  return Boolean(window.__TALELOOM_FIXTURE__)
    || new URLSearchParams(location.search).get('fixture') === '1';
}
