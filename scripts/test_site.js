// Browser tests for the all-roadmaps site. Usage: node scripts/test_site.js http://127.0.0.1:8766/
const { chromium } = require(process.env.PW || 'playwright');
const BASE = process.argv[2] || 'http://127.0.0.1:8766/';
(async () => {
  const R = []; const ok = (n, p, d='') => R.push({ name: n, pass: !!p, detail: String(d) });
  const browser = await chromium.launch({ executablePath: process.env.CHROME || undefined, args: ['--no-sandbox'] });
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  const errs = []; page.on('pageerror', e => errs.push(e.message));
  page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errs.push(m.text()); });
  await page.goto(BASE); await page.waitForSelector('section.topic', { timeout: 20000 });
  const idx = await page.evaluate(() => fetch('data/index.json').then(r => r.json()));
  ok('loads without script errors', errs.length === 0, errs.join(' | '));
  ok('catalogue lists every roadmap', (await page.$$eval('#grid .rm', x => x.length)) === idx.roadmaps.length, idx.roadmaps.length);
  const ads = await page.evaluate(() => fetch('data/r/ai-data-scientist.json').then(r => r.json()));
  const n = ads.topics.reduce((a, t) => a + t.resources.length, 0);
  ok('default roadmap renders one entry per inventory row', (await page.$$eval('#main .item', x => x.length)) === n, n);
  // global search
  await page.fill('#q', 'kubernetes pods'); await page.waitForSelector('#searchCount', { timeout: 15000 });
  const sc = await page.textContent('#searchCount');
  ok('global search returns cross-roadmap results', /^\d+ results/.test(sc) && parseInt(sc) > 0, sc);
  await page.fill('#q', 'zzqx-nothing-here'); await page.waitForTimeout(400);
  ok('search with no match shows empty state', await page.$('#results #emptyState') !== null);
  await page.fill('#q', ''); await page.waitForTimeout(300);
  ok('clearing search hides results', await page.$eval('#results', e => e.hidden));
  // roadmap switch via select + hash
  await page.selectOption('#roadmapSelect', 'ai-agents'); await page.waitForFunction(() => location.hash === '#ai-agents');
  await page.waitForFunction(() => document.querySelector('.rmhead h2')?.textContent.length > 0 && document.querySelector('#grid .rm[aria-current="true"]')?.dataset.slug === 'ai-agents');
  const agents = await page.evaluate(() => fetch('data/r/ai-agents.json').then(r => r.json()));
  ok('roadmap selector switches roadmap', (await page.$$eval('#main .item', x => x.length)) === agents.topics.reduce((a, t) => a + t.resources.length, 0));
  // filters
  await page.click('[data-access="replacement"]'); await page.waitForTimeout(200);
  const kinds = await page.$$eval('#main .item', x => x.map(i => i.dataset.kind));
  ok('Replacements filter shows only replacements', kinds.length > 0 && kinds.every(k => k === 'replacement'), kinds.length);
  const hrefs = await page.$$eval('#main .item .title a', a => a.map(x => x.href));
  ok('replacement entry links to the free course', hrefs.some(h => h.includes('academy.langchain.com')), hrefs.join(' '));
  await page.click('[data-access="free"]'); await page.waitForTimeout(200);
  const k2 = await page.$$eval('#main .item', x => x.map(i => i.dataset.kind));
  ok('Verified-free filter shows only verified items', k2.length > 0 && k2.every(k => k === 'free' || k === 'timelimited'), k2.length);
  await page.click('[data-access="uncertain"]'); await page.waitForTimeout(200);
  const k3 = await page.$$eval('#main .item', x => x.map(i => i.dataset.kind));
  ok('Uncertain filter shows only uncertain items', k3.every(k => k === 'uncertain'), k3.length);
  await page.click('[data-access="all"]'); await page.waitForTimeout(200);
  // nothing unverified shown as FREE
  const bad = await page.$$eval('#main .item', x => x.filter(i => /^FREE$/.test(i.querySelector('.head .pill').textContent) && i.dataset.kind !== 'free').length);
  ok('no unverified item carries a FREE label', bad === 0, bad);
  // topic navigation
  const second = await page.$eval('#nav li:nth-child(5) a', a => a.getAttribute('href'));
  await page.click('#nav li:nth-child(5) a');
  await page.waitForFunction(h => { const el = document.getElementById(h.slice(1)); const r = el.getBoundingClientRect(); return r.top < 300 && r.bottom > 0; }, second, { timeout: 4000 }).catch(() => {});
  const inView = await page.$eval(second, el => { const r = el.getBoundingClientRect(); return r.top < 300 && r.bottom > 0; });
  const cur = await page.$eval('#nav li:nth-child(5) a', a => a.getAttribute('aria-current'));
  ok('topic index scrolls to the topic and marks it', inView && cur === 'true', `${second} ${inView} ${cur}`);
  // deep link
  await page.goto(BASE + '#data-analyst'); await page.waitForFunction(() => document.querySelector('.rmhead h2')?.textContent === 'Data Analyst' || document.querySelector('#grid .rm[aria-current="true"]')?.dataset.slug === 'data-analyst', null, { timeout: 15000 });
  ok('deep link opens that roadmap', (await page.$eval('#roadmapSelect', s => s.value)) === 'data-analyst');
  // progress
  const ids = await page.$$eval('#main .item input[type=checkbox]', x => x.slice(0, 3).map(c => c.id));
  for (const id of ids) await page.check('#' + id);
  await page.reload(); await page.waitForFunction(() => document.querySelector('#roadmapSelect').value === 'data-analyst' && document.querySelectorAll('#main .item').length > 0);
  const kept = await Promise.all(ids.map(id => page.isChecked('#' + id)));
  ok('progress persists across reload', kept.every(Boolean) && (await page.textContent('#progressText')).startsWith('3 /'), kept.join());
  await page.click('#resetProgress'); await page.waitForTimeout(200);
  ok('reset clears this roadmap\'s progress', (await page.textContent('#progressText')).startsWith('0 /'));
  await page.screenshot({ path: 'shot-desktop.png' });
  // storage blocked
  const pb = await (await browser.newContext()).newPage(); const eb = [];
  pb.on('pageerror', e => eb.push(e.message));
  await pb.addInitScript(() => Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocked'); } }));
  await pb.goto(BASE); await pb.waitForSelector('section.topic'); await pb.check('#main .item input[type=checkbox]');
  ok('works when storage is blocked', eb.length === 0, eb.join('|'));
  // mobile dark
  const pm = await (await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: 'dark' })).newPage();
  await pm.goto(BASE + '#ai-engineer'); await pm.waitForSelector('section.topic');
  ok('no horizontal scroll at 390px', (await pm.evaluate(() => document.documentElement.scrollWidth - innerWidth)) <= 0);
  ok('dark theme applies', (await pm.evaluate(() => getComputedStyle(document.body).backgroundColor)) === 'rgb(16, 22, 19)');
  await pm.screenshot({ path: 'shot-mobile-dark.png' });
  await browser.close();
  for (const r of R) console.log(`${r.pass ? 'PASS' : 'FAIL'}  ${r.name}${r.pass ? '' : '  — ' + r.detail}`);
  console.log(`PASSED ${R.filter(r => r.pass).length}/${R.length}`);
  process.exit(R.every(r => r.pass) ? 0 : 1);
})();
