'use strict';
const $ = id => document.getElementById(id);
const themeKey = 'grslot-studio-theme';
const darkMode = $('darkMode');
function setDarkMode(enabled) {
  document.documentElement.dataset.theme = enabled ? 'dark' : 'light';
  darkMode.setAttribute('aria-pressed', String(enabled));
}
try { setDarkMode(localStorage.getItem(themeKey) === 'dark'); } catch {}
darkMode.addEventListener('click', () => {
  const enabled = darkMode.getAttribute('aria-pressed') !== 'true';
  setDarkMode(enabled);
  try { localStorage.setItem(themeKey, enabled ? 'dark' : 'light'); } catch {}
});
const copy = value => JSON.parse(JSON.stringify(value));
const escapeHtml = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let catalog, project, savedProject, currentUid, category = 'all', saving = false, hasSaved = false, toastTimer;
const filmById = new Map();
function film(uid) { return {...filmById.get(uid), ...(project.overrides[uid] || {})}; }
function icon(uid) { return film(uid).icon || '/api/icon/' + uid; }
function selected(uid) { return project.selected.includes(uid); }
function dirty() { return JSON.stringify(project) !== JSON.stringify(savedProject); }
function validName(value) { return value === value.trim() && /^[\x20-\x7e]{1,32}$/.test(value); }
function validateName() {
  const name = $('filmName').value;
  $('filmName').setCustomValidity(name === filmById.get(currentUid).name || validName(name) ? '' : '请输入 1–32 个英文、数字或常用英文符号，首尾不留空格。');
}
function toast(message) {
  $('toast').textContent = message;
  $('toast').hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, 4500);
}
function updateStatus() {
  $('saveStatus').textContent = saving ? '正在保存…' : dirty() ? '有未保存更改' : hasSaved ? '已保存到本机' : '尚未保存';
  $('savedLocation').hidden = !hasSaved;
  $('save').disabled = saving || (hasSaved && !dirty());
  $('discard').disabled = saving || !dirty();
}
function counts() {
  const result = {};
  for (const item of catalog.films) {
    const key = film(item.uid).category;
    result[key] = (result[key] || 0) + 1;
  }
  return result;
}
function renderCategories() {
  const total = counts();
  if (category !== 'all' && !total[category]) category = 'all';
  const entries = [['all', '全部胶片', catalog.films.length], ...Object.entries(catalog.categories).filter(([key]) => total[key]).map(([key, label]) => [key, label, total[key]])];
  $('categories').innerHTML = entries.map(([key, label, count]) => `<button class="category ${key === category ? 'active' : ''}" data-category="${escapeHtml(key)}">${escapeHtml(label)}<span>${count}</span></button>`).join('');
}
function visibleFilms() {
  const search = $('search').value.trim().toLowerCase();
  const group = $('groupFilter').value;
  return catalog.films.filter(original => {
    const item = film(original.uid);
    return (category === 'all' || item.category === category) && (!group || item.group === group) && (!$('selectedOnly').checked || selected(item.uid)) && (!search || [item.name, original.name, item.author, catalog.groups[item.group] || item.group].join(' ').toLowerCase().includes(search));
  });
}
function renderCards() {
  const items = visibleFilms();
  $('libraryTitle').textContent = category === 'all' ? '全部胶片' : catalog.categories[category];
  $('libraryCount').textContent = `${catalog.films.length} 款胶片 · 已勾选 ${project.selected.length} 款` + (items.length !== catalog.films.length ? ` · 当前显示 ${items.length} 款` : '');
  $('filmGrid').innerHTML = items.map(original => {
    const item = film(original.uid);
    const slots = project.slots.map((uid, index) => uid === item.uid ? index + 1 : null).filter(Boolean);
    return `<article class="film-card ${item.uid === currentUid ? 'current' : ''} ${selected(item.uid) ? '' : 'off'}" data-uid="${item.uid}" tabindex="0" role="button" aria-label="编辑 ${escapeHtml(item.name)}" aria-pressed="${item.uid === currentUid}"><label class="card-check"><input type="checkbox" data-toggle="${item.uid}" aria-label="纳入 ${escapeHtml(item.name)}" ${selected(item.uid) ? 'checked' : ''}></label><div class="card-art"><img src="${escapeHtml(icon(item.uid))}" alt="${escapeHtml(item.name)}" loading="lazy"></div><h3>${escapeHtml(item.name)}</h3><p>${escapeHtml(catalog.groups[item.group] || item.group)}</p><div class="card-slot">${slots.length ? 'Slot ' + slots.join(' · ') : '&nbsp;'}</div></article>`;
  }).join('');
  $('empty').hidden = items.length > 0;
}
function optionHtml(ids, chosen) {
  return ids.map(uid => `<option value="${uid}" ${uid === chosen ? 'selected' : ''}>${escapeHtml(film(uid).name)}</option>`).join('');
}
function renderSlots() {
  $('slots').innerHTML = project.slots.map((uid, index) => `<label class="slot-row"><span class="slot-no">0${index + 1}</span><img src="${escapeHtml(icon(uid))}" alt=""><select data-slot="${index}" aria-label="Slot ${index + 1} 默认胶片">${optionHtml(project.selected, uid)}</select></label>`).join('');
}
function renderDetails() {
  const item = film(currentUid);
  $('filmUid').textContent = 'UID ' + currentUid;
  $('detailIcon').src = icon(currentUid);
  $('detailIcon').alt = item.name;
  $('filmName').value = item.name;
  validateName();
  $('filmCategory').value = item.category;
  $('filmSource').textContent = catalog.groups[item.group] || item.group;
  $('filmAuthor').textContent = item.author;
  $('filmNotes').value = item.notes ?? '';
  $('detailSelected').checked = selected(currentUid);
}
function render() { renderCategories(); renderCards(); renderSlots(); renderDetails(); updateStatus(); }
function changed() { renderCategories(); renderCards(); renderSlots(); updateStatus(); }
function override(key, value) {
  const values = project.overrides[currentUid] || {};
  const original = filmById.get(currentUid);
  if (value === original[key] || ((key === 'icon' || key === 'notes') && !value)) delete values[key];
  else values[key] = value;
  if (Object.keys(values).length) project.overrides[currentUid] = values;
  else delete project.overrides[currentUid];
  if (key === 'notes') updateStatus();
  else changed();
}
function toggleFilm(uid, include) {
  if (include) {
    if (!selected(uid)) project.selected.push(uid);
    project.selected.sort((a, b) => catalog.films.findIndex(f => f.uid === a) - catalog.films.findIndex(f => f.uid === b));
    render();
    return;
  }
  const affected = project.slots.map((value, index) => value === uid ? index : null).filter(value => value !== null);
  if (!affected.length) {
    project.selected = project.selected.filter(value => value !== uid);
    render();
    return;
  }
  const alternatives = project.selected.filter(value => value !== uid);
  render();
  if (!alternatives.length) { toast('请至少保留一款胶片供六槽使用。'); return; }
  $('replacementText').textContent = `${film(uid).name} 正用于 ${affected.length} 个默认槽位。替换后可取消勾选，原始胶片资料继续保存在本机。`;
  $('replacementSlots').innerHTML = affected.map(index => `<label class="replacement-row">Slot ${index + 1}<select data-replace-slot="${index}" aria-label="替换 Slot ${index + 1}">${optionHtml(alternatives, alternatives[0])}</select></label>`).join('');
  $('replacement').dataset.uid = uid;
  $('replacement').returnValue = '';
  $('replacement').showModal();
}
async function request(url, options) {
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '操作失败。');
  return result;
}
async function save() {
  if (saving) return;
  const invalid = catalog.films.find(item => {
    const name = project.overrides[item.uid]?.name;
    return name !== undefined && !validName(name);
  });
  if (invalid) {
    currentUid = invalid.uid;
    renderCards();
    renderDetails();
    $('filmName').reportValidity();
    return;
  }
  const snapshot = copy(project);
  saving = true;
  updateStatus();
  try {
    const result = await request('/api/project', {method:'POST', headers:{'Content-Type':'application/json','X-GRSlot-Client':'studio-lite'}, body:JSON.stringify(snapshot)});
    project.revision = result.project.revision;
    savedProject = copy(result.project);
    hasSaved = true;
    toast(dirty() ? '已保存提交时的配置，后续更改仍待保存。' : '项目已保存到本机。');
  } catch (error) { toast(error.message); }
  finally { saving = false; updateStatus(); }
}
async function replaceIcon(file) {
  if (!file) return;
  if (file.size > 5 * 1024 * 1024) { toast('请选择 5MB 以内的图片。'); return; }
  const editingUid = currentUid;
  const url = URL.createObjectURL(file);
  const image = new Image();
  try {
    image.src = url;
    await image.decode();
    if (image.width * image.height > 25000000) throw new Error('图片尺寸过大，请使用较小图片。');
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 40;
    const context = canvas.getContext('2d', {alpha:true});
    const side = Math.min(image.width, image.height);
    context.drawImage(image, (image.width - side) / 2, (image.height - side) / 2, side, side, 0, 0, 40, 40);
    const png = canvas.toDataURL('image/png');
    const values = {...(project.overrides[editingUid] || {}), icon:png};
    delete values.icon_design;
    project.overrides[editingUid] = values;
    changed();
    if (currentUid === editingUid) renderDetails();
  } catch (error) { toast(error.message || '这张图片无法读取。'); }
  finally { URL.revokeObjectURL(url); $('iconFile').value = ''; }
}
$('search').addEventListener('input', renderCards);
$('selectedOnly').addEventListener('change', renderCards);
$('groupFilter').addEventListener('change', renderCards);
$('categories').addEventListener('click', event => {
  const button = event.target.closest('[data-category]');
  if (button) { category = button.dataset.category; renderCategories(); renderCards(); }
});
$('filmGrid').addEventListener('click', event => {
  if (event.target.closest('.card-check')) return;
  const card = event.target.closest('[data-uid]');
  if (card) { currentUid = Number(card.dataset.uid); renderCards(); renderDetails(); }
});
$('filmGrid').addEventListener('keydown', event => {
  const card = event.target;
  if (!card.matches('.film-card') || !['Enter', ' '].includes(event.key)) return;
  event.preventDefault();
  card.click();
  $('filmGrid').querySelector(`.film-card[data-uid="${currentUid}"]`)?.focus();
});
$('filmGrid').addEventListener('change', event => {
  if (event.target.matches('[data-toggle]')) toggleFilm(Number(event.target.dataset.toggle), event.target.checked);
});
$('detailSelected').addEventListener('change', event => toggleFilm(currentUid, event.target.checked));
$('filmName').addEventListener('input', event => {
  const value = event.target.value;
  validateName();
  override('name', value);
});
$('filmNotes').addEventListener('input', event => override('notes', event.target.value));
$('filmCategory').addEventListener('change', event => override('category', event.target.value));
$('details').addEventListener('submit', event => { event.preventDefault(); save(); });
$('restoreDetails').addEventListener('click', () => { delete project.overrides[currentUid]; render(); });
$('slots').addEventListener('change', event => {
  if (event.target.matches('[data-slot]')) { project.slots[Number(event.target.dataset.slot)] = Number(event.target.value); changed(); }
});
$('replacement').addEventListener('close', () => {
  if ($('replacement').returnValue !== 'replace') return;
  for (const choice of $('replacementSlots').querySelectorAll('select')) project.slots[Number(choice.dataset.replaceSlot)] = Number(choice.value);
  project.selected = project.selected.filter(uid => uid !== Number($('replacement').dataset.uid));
  render();
});
const iconEditor = $('iconEditor');
const iconForm = $('iconForm');
const iconCanvas = $('iconPreview');
const defaultIconDesign = {
  brand: 'FILM', small: '', main: '400',
  topInk: '#882d24', topFill: '#fac744',
  smallInk: '#ffffff', mainInk: '#ffffff', bodyFill: '#07539c',
  divider: false, dividerFill: '#e7bf42', strip: false, stripFill: '#6b507f',
};
let iconFontReady = false;

function readIconDesign() {
  return Object.fromEntries([...iconForm.elements].filter(input => input.name).map(input => [
    input.name, input.type === 'checkbox' ? input.checked : input.value.trim(),
  ]));
}

function writeIconDesign(settings) {
  for (const [key, value] of Object.entries(settings)) {
    const input = iconForm.elements.namedItem(key);
    if (input.type === 'checkbox') input.checked = value;
    else input.value = value;
  }
}

function validateIconDesign(design) {
  const keys = Object.keys(defaultIconDesign);
  if (!design || typeof design !== 'object' || Object.keys(design).length !== keys.length ||
      !keys.every(key => Object.hasOwn(design, key))) throw new Error('图标模板字段不完整或格式有误。');
  for (const [key, limit] of [['brand', 10], ['small', 10], ['main', 6]]) {
    const value = design[key];
    if (typeof value !== 'string' || value !== value.trim() ||
        (key !== 'small' && !value) || value.length > limit || /[^A-Za-z0-9 .&+-]/.test(value)) {
      throw new Error('请检查图标文字，只能使用英文字母、数字、空格及 . & + -，并遵守字符上限。');
    }
  }
  for (const key of keys) {
    if (typeof defaultIconDesign[key] === 'boolean' && typeof design[key] !== 'boolean') {
      throw new Error('图标色条开关格式有误。');
    }
    if (typeof defaultIconDesign[key] === 'string' && defaultIconDesign[key].startsWith('#') &&
        (typeof design[key] !== 'string' || !/^#[0-9a-f]{6}$/i.test(design[key]))) {
      throw new Error('图标颜色格式有误。');
    }
  }
}

function paintIcon(design) {
  const context = iconCanvas.getContext('2d');
  context.clearRect(0, 0, 40, 40);
  function rect(color, x, y, width, height) {
    context.fillStyle = color;
    context.fillRect(x, y, width, height);
  }
  function line(text, color, center, maxHeight, minHeight) {
    context.font = '100px "GRSlot Icon Lettering"';
    const size = context.measureText(text);
    const scale = Math.min(32 / (size.actualBoundingBoxLeft + size.actualBoundingBoxRight),
      maxHeight / (size.actualBoundingBoxAscent + size.actualBoundingBoxDescent));
    if ((size.actualBoundingBoxAscent + size.actualBoundingBoxDescent) * scale < minHeight) {
      throw new Error('「' + text + '」太宽，请缩短文字。');
    }
    context.save();
    context.translate(20, center);
    context.scale(scale, scale);
    context.fillStyle = color;
    context.fillText(text, (size.actualBoundingBoxLeft - size.actualBoundingBoxRight) / 2,
      (size.actualBoundingBoxAscent - size.actualBoundingBoxDescent) / 2);
    context.restore();
  }

  rect('#101214', 1, 1, 38, 38);
  rect(design.topFill, 2, 2, 36, 10);
  rect(design.bodyFill, 2, 12, 36, 26);
  if (design.divider) rect(design.dividerFill, 2, 12, 36, 2);
  if (design.strip) rect(design.stripFill, 2, 36, 36, 2);
  const top = design.divider ? 14 : 12;
  const bottom = design.strip ? 36 : 38;
  line(design.brand, design.topInk, 7, 6, 4);
  if (design.small) {
    line(design.small, design.smallInk, top + 5, 6, 4);
    line(design.main, design.mainInk, (top + 10 + bottom) / 2, 11.5, 7);
  } else {
    line(design.main, design.mainInk, (top + bottom) / 2, 13, 7);
  }
}

function previewIcon() {
  const design = readIconDesign();
  const actual = $('iconActual').getContext('2d');
  try {
    if (!iconFontReady) throw new Error('正在加载图标字体…');
    validateIconDesign(design);
    paintIcon(design);
    actual.clearRect(0, 0, 40, 40);
    actual.drawImage(iconCanvas, 0, 0);
    $('iconError').textContent = '';
    $('applyIcon').disabled = false;
    $('saveIconDesign').disabled = false;
    return design;
  } catch (error) {
    iconCanvas.getContext('2d').clearRect(0, 0, 40, 40);
    actual.clearRect(0, 0, 40, 40);
    $('iconError').textContent = error.message;
    $('applyIcon').disabled = true;
    $('saveIconDesign').disabled = true;
  }
}

$('editIcon').addEventListener('click', async () => {
  const settings = film(currentUid).icon_design || defaultIconDesign;
  writeIconDesign(settings);
  iconEditor.showModal();
  previewIcon();
  try {
    const fonts = await document.fonts.load('100px "GRSlot Icon Lettering"');
    if (!fonts.length) throw new Error();
    iconFontReady = true;
    if (iconEditor.open) previewIcon();
  } catch {
    if (iconEditor.open) $('iconError').textContent = '图标字体无法加载，请刷新页面后重试。';
  }
});
$('saveIconDesign').addEventListener('click', async () => {
  const design = previewIcon();
  if (!design) return;
  const filename = film(currentUid).name.replace(/[^A-Za-z0-9_-]+/g, '-').slice(0, 60) + '.grslot-icon.json';
  const blob = new Blob([JSON.stringify({version: 1, design}, null, 2)], {type: 'application/json'});
  try {
    if (window.showSaveFilePicker) {
      const handle = await window.showSaveFilePicker({
        suggestedName: filename,
        types: [{description: 'GRSlot 图标模板', accept: {'application/json': ['.json']}}],
      });
      const writer = await handle.createWritable();
      await writer.write(blob);
      await writer.close();
    } else {
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  } catch (error) {
    if (error.name !== 'AbortError') $('iconError').textContent = '无法另存图标模板。';
  }
});
const iconDesignFile = $('iconDesignFile');
$('loadIconDesign').addEventListener('click', () => iconDesignFile.click());
iconDesignFile.addEventListener('change', async () => {
  const file = iconDesignFile.files[0];
  if (!file) return;
  try {
    if (file.size > 4096) throw new Error('图标模板文件过大。');
    const {version, design} = JSON.parse(await file.text()) ?? {};
    if (!iconEditor.open || iconDesignFile.files[0] !== file) return;
    if (version !== 1) throw new Error('请选择 Studio 另存的图标模板。');
    validateIconDesign(design);
    if (!iconFontReady) throw new Error('字体正在加载，请稍后再试。');
    paintIcon(design);
    writeIconDesign(design);
    previewIcon();
  } catch (error) {
    if (iconEditor.open && iconDesignFile.files[0] === file) {
      previewIcon();
      $('iconError').textContent = error instanceof SyntaxError ? '图标模板不是有效的 JSON 文件。' : error.message;
    }
  } finally {
    if (iconDesignFile.files[0] === file) iconDesignFile.value = '';
  }
});
iconEditor.addEventListener('close', () => { iconDesignFile.value = ''; });
iconForm.addEventListener('input', previewIcon);
$('cancelIcon').addEventListener('click', () => iconEditor.close());
iconForm.addEventListener('submit', event => {
  event.preventDefault();
  const design = previewIcon();
  if (!design) return;
  project.overrides[currentUid] = {
    ...(project.overrides[currentUid] || {}),
    icon: iconCanvas.toDataURL('image/png'),
    icon_design: design,
  };
  iconEditor.close();
  changed();
  renderDetails();
});

$('changeIcon').addEventListener('click', () => $('iconFile').click());
$('iconFile').addEventListener('change', event => replaceIcon(event.target.files[0]));
$('save').addEventListener('click', save);
$('copyPath').addEventListener('click', async () => {
  const field = $('projectPath');
  try {
    await navigator.clipboard.writeText(field.value);
    toast('已复制项目 JSON 路径。');
  } catch {
    field.focus();
    field.select();
    toast('路径已选中，请按 Command-C 复制。');
  }
});
$('discard').addEventListener('click', () => { project = copy(savedProject); render(); });
window.addEventListener('beforeunload', event => { if (project && dirty()) { event.preventDefault(); event.returnValue = ''; } });
request('/api/project').then(data => {
  catalog = data;
  project = copy(data.project);
  savedProject = copy(data.project);
  hasSaved = data.saved;
  $('projectPath').value = data.project_path;
  currentUid = data.films[0].uid;
  for (const item of data.films) filmById.set(item.uid, item);
  $('groupFilter').innerHTML = '<option value="">全部版本</option>' + [...new Set(data.films.map(f => f.group))].map(group => `<option value="${escapeHtml(group)}">${escapeHtml(data.groups[group] || group)}</option>`).join('');
  $('filmCategory').innerHTML = Object.entries(data.categories).map(([key, label]) => `<option value="${escapeHtml(key)}">${escapeHtml(label)}</option>`).join('');
  $('workspace').hidden = false;
  render();
}).catch(error => {
  $('fatal').textContent = error.message;
  $('fatal').hidden = false;
  $('saveStatus').textContent = '读取失败';
});
