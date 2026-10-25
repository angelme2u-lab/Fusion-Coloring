// State-flow checks using the real inline script, without a browser or API calls.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const html = execFileSync('python3', ['-c', 'import folio_press; print(folio_press.HTML)'], {encoding:'utf8'});
const script = html.split('<script>')[1].split('</script>')[0];
class Element {
  constructor(tag = 'div') {
    this.tag = tag; this.value = ''; this.checked = false; this.hidden = false;
    this.dataset = {}; this.children = []; this.files = []; this.style = {};
    this.classList = {toggle(){}, add(){}, remove(){}};
  }
  set innerHTML(value) { this.children = []; }
  appendChild(child) { this.children.push(child); return child; }
  addEventListener() {} removeAttribute() {} click() { this.clickCount = (this.clickCount || 0) + 1; } scrollIntoView() {}
  querySelector(tag) { return this.children.find(c => c.tag === tag); }
  getContext() { return {}; }
}
const elements = new Map();
const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
const inputs = () => get('charchk').children.flatMap(l => l.children).filter(c => c.tag === 'input');
const document = {
  getElementById:get, createElement:tag=>new Element(tag), createTextNode:text=>({text}), body:new Element(),
  querySelectorAll:sel => sel === '#charchk input' ? inputs() : [],
  querySelector:sel => { const match = sel.match(/data-char="([^"]+)"/); return match ? inputs().find(c=>c.dataset.char === match[1]) : null; }
};
let savedBlob, responses = [], requests = [];
class Reader {
  readAsText(file) { this.result = file.text; this.onload(); }
}
class FakeImage {
  constructor() { this.naturalWidth=1024; this.naturalHeight=1536; }
  set src(value) { if (this.onload) this.onload(); }
}
const context = vm.createContext({document, Blob, FileReader:Reader, Image:FakeImage, AbortController,
  setTimeout:()=>1, clearTimeout(){}, console, localStorage:{getItem:()=>null,setItem(){}},
  URL:{createObjectURL:b=>{savedBlob=b;return 'blob:test'},revokeObjectURL(){}},
  fetch:async (url, options) => {
    if (url === '/info') return {json:async()=>({pillow:true})};
    requests.push(JSON.parse(options.body));
    return {ok:true, json:async()=>responses.shift()};
  }
});
const run = code => vm.runInContext(code, context);
get('level').value='medium'; get('key').value='test-only-key';
run(script);
assert.equal(get('quicksavebook').disabled,true);
get('quickloadbook').onclick();
assert.equal(get('loadfile').clickCount,1, 'Top Open saved book opens the file picker directly');

(async()=>{
  run(`styleReference={name:'approved.png',image:'style-pixels'};
       characters=[{id:'c1',name:'Milo',description:'tabby',refs:['identity-pixels']}];
       renderCharacters();`);
  inputs()[0].checked=true;
  get('subject').value='Two cats in a kitchen';
  const generation={model:'gpt-image-2.5-flare',level:'medium',quality:'high',prompt:'FULL PROMPT',subject:get('subject').value,cleanup:true};
  get('cleanup').checked=true;
  responses.push({image:'cleaned-pixels', original_image:'raw-pixels', generation});
  await get('compose').onclick();
  assert.equal(requests[0].style_reference,'style-pixels');
  assert.deepEqual(requests[0].references,['identity-pixels']);
  assert.equal(requests[0].cleanup,true);
  assert.equal(run('book[0].original_image'),'raw-pixels');
  assert.equal(get('generationprompt').value,'FULL PROMPT');
  assert.equal(get('generationdetails').hidden,false);
  assert.equal(get('quicksavebook').disabled,false);

  get('quicksavebook').onclick();
  assert.equal(get('bookdownloadlink').hidden,false);
  assert.equal(get('bookdownloadlink').clickCount,1);
  assert.equal(get('quickbookdownload').hidden,false);
  assert.match(get('booksavestatus').textContent,/download requested/);
  assert.doesNotMatch(get('booksavestatus').textContent,/Book file saved/);
  const saved=JSON.parse(await savedBlob.text());
  assert.equal(saved.version,4);
  assert.equal(saved.pages[0].generation.references.style.name,'approved.png');
  assert.equal(JSON.stringify(saved).includes('test-only-key'),false);
  get('loadfile').files=[{text:JSON.stringify(saved)}];
  get('loadfile').onchange();
  assert.match(get('booktoolbarstatus').textContent,/Book loaded: 1 pages/);
  assert.equal(run('book[0].original_image'),'raw-pixels');
  assert.equal(run('book[0].generation.prompt'),'FULL PROMPT');

  run(`characters=[]; styleReference=null;`);
  get('subject').value='different'; get('level').value='easy';
  get('reusesettings').onclick();
  assert.equal(get('subject').value,generation.subject);
  assert.equal(get('level').value,'medium');
  assert.equal(run('styleReference.image'),'style-pixels');
  assert.equal(inputs()[0].checked,true);
  assert.equal(run('characters.length'),1);
  get('reusesettings').onclick();
  assert.equal(run('characters.length'),1, 'Reuse must not duplicate an existing matching character');

  get('batchlist').value='First scene\nSecond scene';
  for(let i=0;i<2;i++) responses.push({image:'batch-'+i,generation:{...generation,subject:'scene-'+i}});
  await get('batchstart').onclick();
  assert.equal(run('book.length'),3);
  assert.equal(run('book[2].generation.references.style.image'),'style-pixels');
  assert.equal(requests.length,3);

  get('loadfile').files=[{text:JSON.stringify({version:3,pages:[{kind:'art',image:'legacy',caption:'Original artwork'},{kind:'story',body:'Original story'}]})}];
  get('loadfile').onchange();
  assert.equal(run('book.length'),2);
  assert.equal(run('book[0].image'),'legacy');
  assert.equal(run('book[1].body'),'Original story');
  assert.equal(get('generationdetails').hidden,true);
  assert.equal(run('styleReference'),null);
  context.URL.createObjectURL=()=>{throw new Error('download unavailable')};
  get('savebook').onclick();
  assert.match(get('booksavestatus').textContent,/pages are still in this tab/);
  assert.equal(run('book.length'),2, 'A failed download must not remove pages');
  console.log('PASS: single/batch generation, reference snapshots, key exclusion, save/load, settings reuse, and legacy books');
})().catch(error=>{console.error(error);process.exitCode=1});
