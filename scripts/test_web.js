// Browser tests for Darb: production build (real URLs, /darb/ base) and single-file preview (hash routes).
const {chromium}=require(process.env.PW||'playwright');
const PROD=process.env.PROD||'http://localhost:8788/darb/', PREVIEW=process.env.PREVIEW||'http://localhost:8777/_test.html';
let pass=0,fail=0;const ok=(c,m)=>{if(c){pass++;console.log('PASS ',m)}else{fail++;console.log('FAIL ',m)}};
(async()=>{
const b=await chromium.launch({executablePath:process.env.CHROME});
const ctx=await b.newContext({viewport:{width:1280,height:900}});const p=await ctx.newPage();const errs=[];
p.on('pageerror',e=>errs.push(e.message));p.on('console',m=>{if(m.type()==='error')errs.push(m.text())});
const N=async(sel)=>p.$$eval(sel,x=>x.length);
// ---------- production build ----------
await p.goto(PROD);await p.waitForSelector('.pcard');
ok(await N('.pcard')===9,'home: 9 popular paths');
ok(await N('.catcard')>=8,'home: category tiles');
ok((await p.title()).startsWith('Darb'),'home: title');
ok(await p.getAttribute('link[rel=canonical]','href')==='https://abdelrahman08.github.io/darb/','home: canonical');
ok(await N('link[hreflang]')===3,'home: hreflang en/ar/x-default');
ok(!!await p.getAttribute('meta[property="og:image"]','content'),'home: og:image');
await p.click('.catcard[data-cat="lang"]');await p.waitForURL('**/darb/paths/');
ok(await p.getAttribute('#catChips [data-cat="lang"]','aria-pressed')==='true','category tile opens Paths filtered');
const nl=await N('#pgrid .pcard');ok(nl>5&&nl<93,`language filter (${nl})`);
await p.click('#catChips [data-cat=""]');ok(await N('#pgrid .pcard')===93,'all 93 paths listed');
await p.fill('#pq','kubernetes');const nk=await N('#pgrid .pcard');ok(nk>=1&&nk<10,`path search (${nk})`);
await p.fill('#pq','');
await p.click('#pgrid a[href$="/paths/rust/"]');await p.waitForURL('**/paths/rust/');
ok(/Rust · Darb/.test(await p.title()),'path page: title updates on client navigation');
ok(await N('.stage')>=4,'rust path: zero + core + final stages');
ok(/Stage 0/.test(await p.textContent('.stage h2')),'first stage is Stage 0 (from zero)');
ok(/Final stage/.test(await p.textContent('.stage:last-child h2')),'last stage is the final stage');
ok(await N('.ov')===5,'field overview: 5 panels');
ok(await N('.ov .tag')>=6,'overview lists skills and jobs');
const cb=await p.$('.stage .course input');if(cb){await cb.check();ok(/^1 of/.test(await p.textContent('#ptext')),'tick updates progress')}else ok(false,'rust has a checkable course');
await p.reload();await p.waitForSelector('.stage');ok(/^1 of/.test(await p.textContent('#ptext')),'progress persists across reload');
ok(/Rust · Darb/.test(await p.title()),'deep link renders the right page');
await p.click('#resetPath');ok(/^0 of/.test(await p.textContent('#ptext')),'reset clears progress');
await p.goBack();await p.waitForSelector('#pgrid');ok(p.url().endsWith('/darb/paths/'),'browser back works');
await p.goto(PROD+'paths/cybersecurity/');await p.waitForSelector('.track');
ok(await N('.track')===4,'cybersecurity: 4 specialisations');
ok(await N('.track .next a')>=3,'specialisations link to related paths');
await p.click('.track .next a[href$="/paths/linux/"]');await p.waitForURL('**/paths/linux/');ok(true,'specialisation link opens related path');
await p.goto(PROD+'paths/');await p.fill('#pq','penetration');ok(await N('#pgrid .pcard')>=1,'path search finds job titles');
await p.fill('#pq','');
await p.goto(PROD+'courses/');await p.waitForSelector('#list .course');
ok(await N('#list .course')===60,'catalog: first 60 shown');
const more=await p.isVisible('#more');ok(more,'catalog: show more button');
await p.click('#more');ok(await N('#list .course')>60,'show more loads more');
await p.fill('#fq','postgres');const np=await N('#list .course');ok(np>0&&np<20,`catalog search (${np})`);
await p.fill('#fq','');await p.selectOption('#fcost','free');ok(await N('#list .p-open')===0,'evidence filter');
await p.selectOption('#fcost','');await p.selectOption('#fpath','sql');const ns=await N('#list .course');ok(ns>0&&ns<15,`path filter (${ns})`);
await p.goto(PROD);await p.fill('#hq','docker');await p.click('#homeSearch button');await p.waitForURL('**/courses/');
ok(await p.inputValue('#fq')==='docker','home search carries into catalog');
for(const [r,id] of [['cohorts','CLR4YoH0'],['institutions','BqHGGquz'],['sponsor','ZvDPPuai']]){await p.goto(PROD+r+'/');await p.waitForSelector('.cta-card');
  ok((await p.getAttribute('.cta-card a.btn','href')).endsWith(id),`${r}: links to its form`)}
for(const r of ['privacy','terms','method','support']){await p.goto(PROD+r+'/');await p.waitForSelector('main h1');ok((await p.textContent('main')).length>300,`${r} page renders`)}
await p.goto(PROD+'nope/here/');ok(/isn't here/.test(await p.textContent('main')),'unknown URL shows not-found (via 404.html in production)');
// ---------- Arabic ----------
await p.goto(PROD+'ar/');await p.waitForSelector('.pcard');
ok(await p.getAttribute('html','dir')==='rtl'&&await p.getAttribute('html','lang')==='ar','Arabic: rtl + lang');
ok(/كورسات مجانية/.test(await p.textContent('h1')),'Arabic: hero in Arabic');
ok((await p.title()).includes('درب'),'Arabic: title in Arabic');
await p.goto(PROD+'ar/paths/data-analyst/');await p.waitForSelector('.stage');
ok(/محلّل بيانات/.test(await p.textContent('h1')),'Arabic: path title');
ok(/المرحلة/.test(await p.textContent('.stage h2')),'Arabic: stage labels');
ok(/عن هذا المجال/.test(await p.textContent('.overview')),'Arabic: overview');
await p.click('.lang');await p.waitForURL('**/darb/paths/data-analyst/');ok(await p.getAttribute('html','dir')==='ltr','language switch keeps the page');
// ---------- mobile + themes ----------
const m=await b.newPage({viewport:{width:390,height:844}});
for(const r of ['','paths/','paths/frontend/','courses/','cohorts/','ar/','ar/paths/','ar/paths/ai-engineer/','ar/courses/','ar/privacy/']){await m.goto(PROD+r);await m.waitForTimeout(250);
  ok(!(await m.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1)),`no sideways scroll at 390px: /${r}`)}
await m.goto(PROD);await m.click('#menuBtn');ok(await m.isVisible('#nav a[href$="/paths/"]'),'mobile menu opens');
const d=await b.newPage({colorScheme:'dark'});await d.goto(PROD);await d.waitForSelector('.pcard');
ok(await d.evaluate(()=>getComputedStyle(document.body).backgroundColor)==='rgb(12, 20, 23)','dark theme');
const s=await b.newContext();await s.addInitScript(()=>{Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked')}})});
const sp=await s.newPage();await sp.goto(PROD+'paths/backend/');await sp.waitForSelector('.stage');ok(true,'works with storage blocked');
// ---------- preview (hash routes) ----------
const h=await ctx.newPage();await h.goto(PREVIEW);await h.waitForSelector('.pcard');
await h.click('a[href="#path-frontend"]');await h.waitForSelector('.stage');ok(h.url().endsWith('#path-frontend'),'preview: hash routing');
await h.click('.lang');await h.waitForSelector('.stage');ok(await h.getAttribute('html','dir')==='rtl','preview: language switch');
await h.click('.lang');
const real=errs.filter(e=>!/ERR_TUNNEL|ERR_CONNECTION|status of 404/.test(e));ok(real.length===0,'no script errors '+real.join(' | '));
await m.goto(PROD+'ar/');await m.waitForSelector('.pcard');await m.screenshot({path:'/tmp/claude-0/m_ar.png'});
await p.goto(PROD);await p.waitForSelector('.pcard');await p.screenshot({path:'/tmp/claude-0/home.png',fullPage:true});
await p.goto(PROD+'ar/paths/frontend/');await p.waitForSelector('.stage');await p.screenshot({path:'/tmp/claude-0/ar_path.png'});
console.log(`PASSED ${pass}/${pass+fail}`);await b.close();process.exit(fail?1:0)})();
