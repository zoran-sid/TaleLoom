/**
 * 影像模式的调查台：观察点、各栏作答、提示与核对结果的动画。负责人：ZC。
 *
 * 只把快照里的 mystery:inspect / mystery:solve / mystery:hint 动作演成可操作的桌面：
 * 提交的答案一律交给 Python 判定（会话返回“【核对完成】”才算通过），动画只在结果
 * 回来之后播放，跳过动画不会跳过判定。草稿答案只存在本页，刷新后按快照重新开始作答；
 * 已查看的地方、尝试次数与已给出的提示保存在游戏状态里。
 *
 * 排序类单元可以拖动；同一操作也能点击完成（点卡片依次放入，点已放的卡片移回），
 * 键盘：Enter／空格放入，↑↓ 调整位置，Delete 移回。选择类单元用单选／多选按钮。
 */
import { gsap } from 'gsap';
import { Flip } from 'gsap/Flip';
import { Draggable } from 'gsap/Draggable';

gsap.registerPlugin(Flip, Draggable);

// 呈现方式（不影响判定）：order 为排先后，pick 为从同一组里挑几项，其余按栏单选。
const LAYOUT = { timeline: 'order', vat: 'order', box: 'order', weight: 'pick', sleeve: 'pick', batch: 'pick' };
// 观察某些单元时的拟音。
const SPOT_SOUND = { vat: 'water', weight: 'water', lamp: 'paper', paper: 'paper', roster: 'paper', batch: 'paper' };

let reduced = false;
gsap.matchMedia().add('(prefers-reduced-motion: reduce)', () => {
  reduced = true;
  return () => { reduced = false; };
});

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

/** 从快照动作里读出当前场景的调查单元；没有时返回 null。 */
export function unitFrom(view) {
  const find = (id) => view.actions.find((a) => a.id === id);
  const solve = find('mystery:solve');
  const inspect = find('mystery:inspect');
  const hint = find('mystery:hint');
  if (!solve && !inspect) return null;
  const [unitParam, ...slots] = solve ? solve.parameters : [];
  const unitOption = unitParam?.options[0];
  const id = unitOption?.id || inspect.parameters[0].options[0].id.split('/')[0];
  const spots = (inspect?.parameters[0].options || []).filter((o) => o.id.startsWith(`${id}/`));
  const hintOption = hint?.parameters[0].options.find((o) => o.id === id);
  return {
    id,
    name: unitOption ? unitOption.label : view.scene_title,
    tries: unitOption?.description || '',
    layout: LAYOUT[id] || 'classify',
    spots,
    slots,
    solvable: Boolean(solve),
    ready: Boolean(solve?.enabled),
    waiting: solve && !solve.enabled ? solve.disabled_reason : '',
    hint: hintOption ? { label: hintOption.label, texts: hintOption.description ? hintOption.description.split('\n') : [], more: hint.enabled } : null,
  };
}

export class Desk {
  /**
   * @param {HTMLElement} root  调查台容器（初始 hidden）
   * @param {{ send: Function, sound: object, speed: Function, onClose: Function }} hooks
   *   send(actionId, values) 返回会话结果；speed(ms) 返回考虑快速模式后的毫秒数。
   */
  constructor(root, { send, sound, speed, onClose }) {
    this.root = root;
    this.send = send;
    this.sound = sound;
    this.speed = speed;
    this.onClose = onClose;
    this.unit = null;
    this.drafts = new Map();
    this.logs = new Map();
    this.feedback = '';
    this.draggables = [];
    this.busy = false;
    this.celebration = null;
    root.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        this.close();
      }
    });
  }

  get open() { return !this.root.hidden; }

  /** 打开调查台；已经打开时只刷新内容。 */
  show(view) {
    const unit = unitFrom(view);
    if (!unit) return false;
    const opening = !this.open;
    if (unit.id !== this.unit?.id) this.feedback = '';
    this.unit = unit;
    this.render();
    if (opening) {
      this.root.hidden = false;
      this.sound.paper?.();
      const sheet = this.root.querySelector('.desk-sheet');
      gsap.fromTo(this.root, { autoAlpha: 0 }, { autoAlpha: 1, duration: this.dur(0.3) });
      gsap.fromTo(sheet, { y: 28 }, { y: 0, duration: this.dur(0.45), ease: 'power3.out' });
      gsap.from(this.root.querySelectorAll('.desk-spot, .slot, .seq-slot'), {
        autoAlpha: 0, y: 10, duration: this.dur(0.3), stagger: this.dur(0.04), ease: 'power2.out', clearProps: 'all',
      });
      (this.root.querySelector('.desk-spot:not(.seen)') || this.root.querySelector('input, .tile, .desk-submit'))
        ?.focus({ preventScroll: true });
    }
    return true;
  }

  /** 快照更新后刷新（不改变打开状态）。 */
  refresh(view) {
    if (!this.open) return;
    const unit = unitFrom(view);
    if (!unit) return this.close(true);
    this.unit = unit;
    this.render();
  }

  close(silent = false) {
    if (!this.open) return;
    this.killDrag();
    this.celebration?.progress(1);
    this.root.hidden = true;
    gsap.set(this.root, { clearProps: 'all' });
    if (!silent) this.onClose?.();
  }

  /** 恢复存档或重新开始时，丢弃旧时间线的本地草稿与观察记录。 */
  reset() {
    this.close(true);
    this.drafts.clear();
    this.logs.clear();
    this.feedback = '';
    this.unit = null;
  }

  dur(seconds) {
    if (reduced) return 0;
    return this.speed(seconds * 1000) / 1000;
  }

  draft() {
    const { id, slots } = this.unit;
    const saved = this.drafts.get(id) || {};
    const clean = {};
    for (const slot of slots) {
      if (slot.options.some((o) => o.id === saved[slot.key])) clean[slot.key] = saved[slot.key];
    }
    this.drafts.set(id, clean);
    return clean;
  }

  setDraft(values, { flip = false } = {}) {
    const state = flip && !reduced ? Flip.getState(this.root.querySelectorAll('.tile')) : null;
    this.drafts.set(this.unit.id, values);
    this.render();
    if (state) Flip.from(state, { duration: this.dur(0.35), ease: 'power2.inOut', absolute: false, targets: this.root.querySelectorAll('.tile') });
  }

  log(lines, kind = 'seen') {
    const list = this.logs.get(this.unit.id) || [];
    for (const text of lines) list.push({ text, kind });
    this.logs.set(this.unit.id, list.slice(-12));
  }

  // ---------- 绘制 ----------

  render() {
    this.killDrag();
    const u = this.unit;
    const sheet = el('div', 'desk-sheet');
    const head = el('header', 'desk-head');
    const titles = el('div', 'desk-titles');
    titles.append(el('p', 'desk-kicker', u.solvable ? '调查 · 核对' : '调查 · 细看'), el('h2', 'desk-title', u.name));
    head.append(titles);
    if (u.tries) head.append(el('span', 'desk-tries', u.tries));
    const done = !u.solvable && u.spots.every((spot) => spot.description === '已查看');
    const leave = el('button', `desk-close${done ? ' done' : ''}`, done ? '看完了' : '暂离');
    leave.type = 'button';
    leave.title = '回到场景（Esc）；已填的答案会保留';
    leave.addEventListener('click', () => this.close());
    head.append(leave);
    sheet.append(head);

    if (u.spots.length) sheet.append(this.renderSpots());
    const log = el('ol', 'desk-log');
    log.setAttribute('aria-live', 'polite');
    for (const entry of this.logs.get(u.id) || []) log.append(el('li', `desk-entry ${entry.kind}`, entry.text));
    if (log.children.length) sheet.append(log);

    if (u.solvable) {
      if (u.waiting) sheet.append(el('p', 'desk-waiting', u.waiting));
      sheet.append(u.layout === 'order' ? this.renderOrder() : this.renderSlots());
    }
    const feedback = el('p', `desk-feedback${this.feedback ? ' bad' : ''}`, this.feedback);
    feedback.setAttribute('role', 'status');
    sheet.append(feedback);
    if (u.hint?.texts.length) {
      const hints = el('ol', 'desk-hints');
      u.hint.texts.forEach((text) => hints.append(el('li', '', text)));
      sheet.append(hints);
    }
    const actions = el('footer', 'desk-actions');
    if (u.solvable) {
      const submit = el('button', 'desk-submit', '核对');
      submit.type = 'button';
      submit.disabled = !u.ready;
      submit.addEventListener('click', () => this.submit());
      actions.append(submit);
    }
    if (u.hint) {
      const hint = el('button', 'desk-hint', u.hint.more ? `给我提示（${u.hint.label.replace('提示 ', '')}）` : '提示已全部给出');
      hint.type = 'button';
      hint.disabled = !u.hint.more;
      hint.addEventListener('click', () => this.askHint());
      actions.append(hint);
    }
    if (actions.children.length) sheet.append(actions);
    sheet.append(el('div', 'desk-stamp', '核对无误'));
    this.root.replaceChildren(sheet);
    if (u.layout === 'order') this.makeDraggable();
  }

  renderSpots() {
    const box = el('section', 'desk-section');
    box.append(el('h3', 'desk-heading', '细看'));
    const row = el('div', 'desk-spots');
    for (const spot of this.unit.spots) {
      const seen = spot.description === '已查看';
      const button = el('button', `desk-spot${seen ? ' seen' : ''}`);
      button.type = 'button';
      button.dataset.spot = spot.id;
      button.append(el('span', 'mark', seen ? '✓' : '○'), el('span', '', spot.label));
      button.setAttribute('aria-label', `${spot.label}${seen ? '（已查看，可重读）' : ''}`);
      button.addEventListener('click', () => this.inspect(spot.id));
      row.append(button);
    }
    box.append(row);
    return box;
  }

  renderSlots() {
    const box = el('section', 'desk-section desk-slots');
    const draft = this.draft();
    const slots = this.unit.slots;
    let rest = slots;
    if (this.unit.layout === 'pick') {
      const same = (s) => s.options.map((o) => o.id).join() === slots[0].options.map((o) => o.id).join();
      const group = slots.filter(same);
      rest = slots.filter((s) => !same(s));
      box.append(this.renderPick(group, draft));
    }
    for (const slot of rest) {
      const field = el('fieldset', 'slot');
      field.append(el('legend', '', slot.label));
      const chips = el('div', 'chips');
      for (const option of slot.options) {
        const chip = el('label', `chip${draft[slot.key] === option.id ? ' on' : ''}`);
        const input = el('input');
        input.type = 'radio';
        input.name = `slot-${slot.key}`;
        input.value = option.id;
        input.checked = draft[slot.key] === option.id;
        input.addEventListener('change', () => {
          this.sound.pen?.();
          this.feedback = '';
          this.setDraft({ ...this.draft(), [slot.key]: option.id });
          this.root.querySelector(`input[name="slot-${slot.key}"][value="${option.id}"]`)?.focus({ preventScroll: true });
        });
        chip.append(input, el('span', '', option.label));
        chips.append(chip);
      }
      field.append(chips);
      box.append(field);
    }
    return box;
  }

  /** 从同一组选项里挑出 k 项：多选，超过上限时最早选的那项让位。 */
  renderPick(group, draft) {
    const field = el('fieldset', 'slot');
    const picked = group.map((s) => draft[s.key]).filter(Boolean);
    field.append(el('legend', '', `${group.map((s) => s.label).join('、')}（选 ${group.length} 项）`));
    const chips = el('div', 'chips');
    for (const option of group[0].options) {
      const on = picked.includes(option.id);
      const chip = el('label', `chip${on ? ' on' : ''}`);
      const input = el('input');
      input.type = 'checkbox';
      input.value = option.id;
      input.checked = on;
      input.addEventListener('change', () => {
        this.sound.pen?.();
        this.feedback = '';
        let next = picked.filter((id) => id !== option.id);
        if (input.checked) next = [...next, option.id].slice(-group.length);
        const values = { ...this.draft() };
        group.forEach((slot, i) => { if (next[i]) values[slot.key] = next[i]; else delete values[slot.key]; });
        this.setDraft(values);
        this.root.querySelector(`input[type="checkbox"][value="${option.id}"]`)?.focus({ preventScroll: true });
      });
      chip.append(input, el('span', '', option.label));
      chips.append(chip);
    }
    field.append(chips);
    return field;
  }

  /** 排先后：已放入的卡片在编号栏里，其余在下方卡池。 */
  renderOrder() {
    const box = el('section', 'desk-section desk-order');
    const draft = this.draft();
    const slots = this.unit.slots;
    box.append(el('p', 'desk-help', '点卡片依次放入，或拖到编号栏；点已放的卡片移回。键盘：Enter 放入，↑↓ 调整，Delete 移回。'));
    const list = el('ol', 'seq');
    slots.forEach((slot, index) => {
      const item = el('li', 'seq-slot');
      item.dataset.slot = slot.key;
      item.append(el('span', 'seq-num', slot.label));
      const placed = draft[slot.key];
      if (placed) {
        item.append(this.card(slot.options.find((o) => o.id === placed), index));
      } else {
        item.append(el('span', 'seq-empty', '空'));
      }
      list.append(item);
    });
    const pool = el('div', 'seq-pool');
    pool.dataset.pool = '1';
    const used = new Set(Object.values(draft));
    for (const option of slots[0].options) {
      if (!used.has(option.id)) pool.append(this.card(option, -1));
    }
    if (!pool.children.length) pool.append(el('span', 'seq-empty', '卡片都已放入'));
    box.append(list, pool);
    return box;
  }

  card(option, index) {
    const card = el('button', 'tile', option.label);
    card.type = 'button';
    card.dataset.flipId = option.id;
    card.dataset.option = option.id;
    card.dataset.index = String(index);
    card.setAttribute('aria-label', index < 0 ? `${option.label}：放入下一个空位` : `${option.label}：第 ${index + 1} 位，点击移回`);
    card.addEventListener('click', () => {
      if (card.dataset.dragged === '1') return;
      if (index < 0) this.place(option.id);
      else this.unplace(index);
    });
    card.addEventListener('keydown', (event) => {
      if (index < 0) return;
      if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') { event.preventDefault(); this.move(index, -1); }
      else if (event.key === 'ArrowDown' || event.key === 'ArrowRight') { event.preventDefault(); this.move(index, 1); }
      else if (event.key === 'Delete' || event.key === 'Backspace') { event.preventDefault(); this.unplace(index); }
    });
    return card;
  }

  orderList() {
    const draft = this.draft();
    return this.unit.slots.map((s) => draft[s.key] || null);
  }

  saveOrder(list, focusId) {
    const values = {};
    this.unit.slots.forEach((slot, i) => { if (list[i]) values[slot.key] = list[i]; });
    this.sound.pen?.();
    this.feedback = '';
    this.setDraft(values, { flip: true });
    if (focusId) this.root.querySelector(`.tile[data-option="${focusId}"]`)?.focus({ preventScroll: true });
  }

  place(optionId, at = -1) {
    const list = this.orderList().map((id) => (id === optionId ? null : id));
    const index = at >= 0 ? at : list.indexOf(null);
    if (index < 0) return;
    const displaced = list[index];
    list[index] = optionId;
    if (displaced) {
      const from = this.orderList().indexOf(optionId);
      if (from >= 0) list[from] = displaced;
    }
    this.saveOrder(list, optionId);
  }

  unplace(index) {
    const list = this.orderList();
    const id = list[index];
    list[index] = null;
    this.saveOrder(list);
    this.root.querySelector(`.tile[data-option="${id}"]`)?.focus({ preventScroll: true });
  }

  move(index, step) {
    const list = this.orderList();
    const target = index + step;
    if (target < 0 || target >= list.length) return;
    [list[index], list[target]] = [list[target], list[index]];
    this.saveOrder(list, list[target]);
  }

  makeDraggable() {
    const slots = [...this.root.querySelectorAll('.seq-slot')];
    const pool = this.root.querySelector('.seq-pool');
    for (const card of this.root.querySelectorAll('.tile')) {
      const [drag] = Draggable.create(card, {
        type: 'x,y',
        zIndexBoost: true,
        minimumMovement: 6,
        onDragStart() { card.dataset.dragged = '1'; card.classList.add('dragging'); },
        onRelease: () => {
          card.classList.remove('dragging');
          if (card.dataset.dragged !== '1') return;
          setTimeout(() => { delete card.dataset.dragged; }, 0);
          const id = card.dataset.option;
          const target = slots.findIndex((slot) => drag.hitTest(slot, '40%'));
          if (target >= 0) return this.place(id, target);
          if (drag.hitTest(pool, '30%') && Number(card.dataset.index) >= 0) return this.unplace(Number(card.dataset.index));
          gsap.to(card, { x: 0, y: 0, duration: this.dur(0.25), ease: 'power2.out' });
        },
      });
      this.draggables.push(drag);
    }
  }

  killDrag() {
    this.draggables.forEach((d) => d.kill());
    this.draggables = [];
  }

  // ---------- 与会话通信 ----------

  async inspect(spot) {
    if (this.busy) return;
    this.busy = true;
    try {
      const sfx = SPOT_SOUND[this.unit.id] || 'paper';
      this.sound[sfx]?.();
      const result = await this.send('mystery:inspect', { spot });
      if (!result) return;
      this.log(result.messages.filter((m) => !m.startsWith('【获得线索】')).map((m) => m.replace(/^【查看】/, '· ')));
      this.noteClues(result.messages);
      this.feedback = result.error_code ? result.messages.join(' ') : '';
      this.refresh(result.view);
      this.root.querySelector('.desk-log li:last-child')?.scrollIntoView({ block: 'nearest' });
    } finally {
      this.busy = false;
    }
  }

  async askHint() {
    if (this.busy) return;
    this.busy = true;
    try {
      const result = await this.send('mystery:hint', { unit: this.unit.id });
      if (!result) return;
      this.feedback = result.error_code ? result.messages.join(' ') : '';
      this.refresh(result.view);
      const last = this.root.querySelector('.desk-hints li:last-child');
      if (last) gsap.from(last, { autoAlpha: 0, x: -12, duration: this.dur(0.4), ease: 'power2.out' });
    } finally {
      this.busy = false;
    }
  }

  async submit() {
    if (this.busy) return;
    const draft = this.draft();
    const missing = this.unit.slots.filter((s) => !draft[s.key]).map((s) => s.label);
    if (missing.length) {
      this.feedback = `还没有填：${missing.join('、')}。`;
      this.render();
      return;
    }
    this.busy = true;
    try {
      const values = { unit: this.unit.id, ...draft };
      const result = await this.send('mystery:solve', values);
      if (!result) return;
      if (!result.error_code && result.messages.some((m) => m.startsWith('【核对完成】'))) {
        this.drafts.delete(this.unit.id);
        this.feedback = '';
        return 'solved';
      }
      this.feedback = result.messages.filter((m) => !m.startsWith('【')).join(' ') || '这一步没能完成。';
      this.refresh(result.view);
      this.wrong();
      return 'retry';
    } finally {
      this.busy = false;
    }
  }

  noteClues(messages) {
    const found = messages.filter((m) => m.startsWith('【获得线索】'));
    if (!found.length) return;
    this.sound.bell?.();
    this.log(found.map((m) => `记入笔记：${m.replace(/^【获得线索】/, '').split('：')[0]}`), 'clue');
  }

  // ---------- 结果动画（只在 Python 判定之后播放） ----------

  wrong() {
    this.sound.wrong?.();
    const sheet = this.root.querySelector('.desk-sheet');
    const line = this.root.querySelector('.desk-feedback');
    if (line) gsap.from(line, { autoAlpha: 0, y: 6, duration: this.dur(0.3) });
    if (!reduced && sheet) gsap.to(sheet, { keyframes: { x: [-9, 8, -5, 3, 0] }, duration: this.dur(0.42), ease: 'none' });
  }

  /** 核对通过：落章、卡片归位，然后合上。点击或按空格可以直接播完。 */
  celebrate() {
    this.drafts.delete(this.unit.id);
    this.feedback = '';
    this.sound.stamp?.();
    const stamp = this.root.querySelector('.desk-stamp');
    const cards = this.root.querySelectorAll('.tile, .chip.on');
    const tl = gsap.timeline({ defaults: { ease: 'power2.out' } });
    tl.to(cards, { scale: 1.04, duration: this.dur(0.18), stagger: this.dur(0.03) })
      .to(cards, { scale: 1, duration: this.dur(0.2) }, '>')
      .fromTo(stamp, { autoAlpha: 0, scale: 2.3, rotation: -18 },
        { autoAlpha: 1, scale: 1, rotation: -7, duration: this.dur(0.45), ease: 'back.out(2.2)' }, '<')
      .to({}, { duration: this.dur(0.7) })
      .to(this.root, { autoAlpha: 0, duration: this.dur(0.35) });
    this.celebration = tl;
    const skip = (event) => {
      if (event.type === 'keydown' && event.key !== ' ' && event.key !== 'Enter') return;
      tl.progress(1);
    };
    this.root.addEventListener('click', skip);
    document.addEventListener('keydown', skip);
    return tl.then(() => {
      this.root.removeEventListener('click', skip);
      document.removeEventListener('keydown', skip);
      this.celebration = null;
      this.close(true);
    });
  }
}
