// Build the production site into web/_site: one HTML file per route and language, with its own
// title, description, canonical, hreflang and Open Graph tags; shared app.css/app.js; sitemap; robots; 404.
import fs from "node:fs"; import path from "node:path"; import vm from "node:vm";
const W = "web", OUT = "web/_site";
const tpl = fs.readFileSync(`${W}/index.html`, "utf8");
const cat = JSON.parse(fs.readFileSync(`${W}/data/catalog.json`, "utf8"));
const site = cat.site, BASE = site.basePath, URL0 = site.siteUrl.replace(/\/?$/, "/");
const css = tpl.match(/<style>([\s\S]*?)<\/style>/)[1];
const js = tpl.match(/<script>\n?([\s\S]*?)<\/script>\s*$/)[1];
const fonts = [...tpl.matchAll(/<link rel="(?:preconnect|stylesheet)"[^>]*>/g)].map(m => m[0]).join("\n");
const body = tpl.slice(tpl.indexOf("</style>") + 8, tpl.lastIndexOf("<script>")).trim();
// Pull the UI strings out of the app so titles match what the page shows.
const tSrc = js.match(/const T=(\{[\s\S]*?\n\}\});/)[1];
const T = vm.runInNewContext("(" + tSrc + ")");
const esc = s => String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
const pages = ["", "paths", "courses", "cohorts", "institutions", "sponsor", "support", "method", "privacy", "terms",
  ...cat.paths.map(p => "paths/" + p.id)];
const rel = (lang, r) => (lang === "ar" ? "ar/" : "") + (r ? r + "/" : "");
function meta(lang, r) {
  const L = T[lang], n = cat.paths.length;
  if (r.startsWith("paths/")) {
    const p = cat.paths.find(x => x.id === r.slice(6)), ids = new Set(p.stages.flatMap(s => s.courses));
    const tt = lang === "ar" ? p.title_ar : p.title, f = lang === "ar" ? p.for_ar : p.for;
    return [`${tt} · Darb`, L.page_desc_path.replace("{t}", tt).replace("{f}", f).replace("{n}", ids.size).replace("{s}", p.stages.length)];
  }
  const k = r || "home";
  return [k === "home" ? L.titles.home : `${L.titles[k]} · Darb`, L.descs[k].replace("{p}", n)];
}
function page(lang, r, notFound) {
  const [title, desc] = notFound ? [`${T[lang].titles.nf} · Darb`, T[lang].descs.nf] : meta(lang, r);
  const url = URL0 + rel(lang, r);
  const alt = notFound ? "" : ["en", "ar"].map(l => `<link rel="alternate" hreflang="${l}" href="${URL0 + rel(l, r)}">`).join("\n") +
    `\n<link rel="alternate" hreflang="x-default" href="${URL0 + rel("en", r)}">\n<link rel="canonical" href="${url}">`;
  const ld = !notFound && r === "" ? `<script type="application/ld+json">${JSON.stringify({"@context": "https://schema.org", "@type": "WebSite", name: site.name, url: URL0, inLanguage: ["en", "ar"]})}</script>` : "";
  return `<!doctype html>
<html lang="${lang}" dir="${lang === "ar" ? "rtl" : "ltr"}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>${esc(title)}</title>
<meta name="description" content="${esc(desc)}">
<meta name="darb-base" content="${BASE}">
<meta name="theme-color" content="#0b5671">
${notFound ? '<meta name="robots" content="noindex">' : alt}
<meta property="og:type" content="website">
<meta property="og:site_name" content="${site.name}">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(desc)}">
<meta property="og:url" content="${url}">
<meta property="og:image" content="${URL0}og.png">
<meta property="og:locale" content="${lang === "ar" ? "ar_EG" : "en_US"}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="${BASE}favicon.svg" type="image/svg+xml">
${fonts}
<link rel="stylesheet" href="${BASE}app.css">
${ld}
</head>
<body>
${body}
<script src="${BASE}app.js" defer></script>
</body>
</html>
`;
}
fs.rmSync(OUT, { recursive: true, force: true });
const write = (f, s) => { fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, s); };
write(`${OUT}/app.css`, ":root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}img{max-width:100%}[hidden]{display:none!important}\n" + css);
write(`${OUT}/app.js`, js);
let count = 0;
for (const lang of ["en", "ar"]) for (const r of pages) { write(`${OUT}/${rel(lang, r)}index.html`, page(lang, r, false)); count++; }
write(`${OUT}/404.html`, page("en", "", true));
for (const f of ["favicon.svg", "og.png"]) if (fs.existsSync(`${W}/${f}`)) fs.copyFileSync(`${W}/${f}`, `${OUT}/${f}`);
write(`${OUT}/data/catalog.json`, fs.readFileSync(`${W}/data/catalog.json`));
const today = cat.built_at.slice(0, 10);
write(`${OUT}/sitemap.xml`, `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n` +
  ["en", "ar"].flatMap(l => pages.map(r => `<url><loc>${URL0 + rel(l, r)}</loc><lastmod>${today}</lastmod>` +
    ["en", "ar"].map(x => `<xhtml:link rel="alternate" hreflang="${x}" href="${URL0 + rel(x, r)}"/>`).join("") + `</url>`)).join("\n") + "\n</urlset>\n");
write(`${OUT}/robots.txt`, `User-agent: *\nAllow: /\nSitemap: ${URL0}sitemap.xml\n`);
write(`${OUT}/.nojekyll`, "");
console.log(`built ${count} pages + 404 into ${OUT} (base ${BASE})`);
