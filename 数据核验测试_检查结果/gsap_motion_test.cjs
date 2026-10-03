// 不启动浏览器的控制器生命周期测试：重复挂载、系统设置与清理。
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname, '../功能组件_页面共用代码/motion.js'), 'utf8');
let binds = 0, unbinds = 0, observers = 0, disconnected = 0, reverted = 0, killed = 0, mediaCallback;
const body = {nodeType: 1, matches: () => false, querySelectorAll: () => []};
const handlers = {}, moves = [];
const document = {documentElement: {dataset: {}}, body, querySelectorAll: () => [],
  addEventListener(type, fn) {binds++; handlers[type] = fn;}, removeEventListener() {unbinds++;}};
const g = {fromTo() {}, to(target) {moves.push(target);}, set() {}, killTweensOf() {killed++;}, matchMedia() {
  return {add(_, callback) {mediaCallback = callback; callback({conditions: {reduce: false}});}, revert() {reverted++;}};
}};
const context = vm.createContext({window: {gsap: g}, document,
  matchMedia: () => ({matches: true}), requestAnimationFrame: () => 1, cancelAnimationFrame() {},
  IntersectionObserver: class {observe() {} unobserve() {} disconnect() {disconnected++;}},
  MutationObserver: class {constructor() {observers++;} observe() {} disconnect() {disconnected++;}}});
vm.runInContext(code, context);
assert.equal(binds, 6); assert.equal(observers, 1);
vm.runInContext(code, context);
assert.equal(binds, 6); assert.equal(observers, 1); // Streamlit 再运行不重复注册
handlers.pointerup();
assert.equal(moves.length, 0); // 未按按钮时，不触发全站按钮动画
const button = {isConnected: true, matches: selector => !selector.includes(':disabled')};
handlers.pointerdown({target: {closest: selector => selector.startsWith('input') ? null : button}});
handlers.pointerup();
assert.equal(moves.length, 2); assert.equal(moves[0], button);
assert.equal(moves[1].length, 1); assert.equal(moves[1][0], button);
handlers.pointerup(); assert.equal(moves.length, 2); // 状态已清理，不重复动画
mediaCallback({conditions: {reduce: true}});
assert.equal(document.documentElement.dataset.ylMotionReduced, 'true'); assert.equal(killed, 1);
context.window.__ylMotion.dispose();
assert.equal(unbinds, 6); assert.equal(disconnected, 2); assert.equal(reverted, 1);
assert.equal(document.documentElement.dataset.ylMotion, undefined);
console.log('GSAP 生命周期、减少动态效果与清理检查通过');
