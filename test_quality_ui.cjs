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
  addEventListener() {} removeAttribute(name) { delete this[name]; } setAttribute(name,value) { this[name]=value; }
  click() { this.clickCount = (this.clickCount || 0) + 1; } scrollIntoView() { this.scrollCalls=(this.scrollCalls||0)+1; }
  focus() { document.activeElement=this; }
  querySelector(tag) { return this.children.find(c => c.tag === tag); }
  getContext() { return {}; }
}
const elements = new Map();
const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
const inputs = () => get('charchk').children.flatMap(l => l.children).filter(c => c.tag === 'input');
const handlers = {};
const document = {
  addEventListener(name,fn){const previous=handlers[name];handlers[name]=event=>{if(previous) previous(event);fn(event);};},
  getElementById:get, createElement:tag=>new Element(tag), createTextNode:text=>({text}), body:new Element(),
  querySelectorAll:sel => sel === '#charchk input' ? inputs() : sel === '.thumbs button' ? get('thumbs').children : [],
  querySelector:sel => { if(sel === '.enlarge-hint') return get('enlargehint'); const match = sel.match(/data-char="([^"]+)"/); return match ? inputs().find(c=>c.dataset.char === match[1]) : null; }
};
let savedBlob, responses = [], requests = [];
class Reader {
  readAsText(file) { this.result = file.text; return this.onload(); }
}
class FakeImage {
  constructor() { this.naturalWidth=1024; this.naturalHeight=1536; }
  set src(value) { if (this.onload) this.onload(); }
}
const context = vm.createContext({document, Blob, FileReader:Reader, Image:FakeImage, AbortController,
  window:{matchMedia:()=>({matches:false}),addEventListener(){}}, confirm:()=>true,
  setTimeout:()=>1, clearTimeout(){}, console, localStorage:{getItem:()=>null,setItem(){}},
  URL:{createObjectURL:b=>{savedBlob=b;return 'blob:test'},revokeObjectURL(){}},
  fetch:async (url, options) => {
    if (url === '/info') return {json:async()=>({pillow:true})};
    requests.push(JSON.parse(options.body));
    return {ok:true, json:async()=>responses.shift()};
  }
});
const run = code => vm.runInContext(code, context);
get('level').value='medium'; get('key').value='test-only-key'; get('creationsmodal').hidden=true;
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
  assert.match(get('bookbackupstate').textContent,/no backup yet/);

  get('quicksavebook').onclick();
  assert.equal(get('bookdownloadlink').hidden,false);
  assert.equal(get('bookdownloadlink').clickCount,1);
  assert.equal(get('quickbookdownload').hidden,false);
  assert.match(get('bookbackupstate').textContent,/Backup download requested at/);
  assert.match(get('booksavestatus').textContent,/download requested/);
  assert.doesNotMatch(get('booksavestatus').textContent,/Book file saved/);
  const saved=JSON.parse(await savedBlob.text());
  assert.equal(saved.version,4);
  assert.equal(saved.pages[0].generation.references.style.name,'approved.png');
  assert.equal(JSON.stringify(saved).includes('test-only-key'),false);
  get('loadfile').files=[{name:'My cats-2.json',text:JSON.stringify(saved)}];
  await get('loadfile').onchange();
  assert.match(get('booktoolbarstatus').textContent,/Book loaded: 1 pages/);
  assert.match(get('bookidentity').textContent,/My cats-2.json.*1 page/);
  assert.match(get('bookbackupstate').textContent,/Reopened successfully.*No changes since reopening/);
  assert.equal(get('quickbookdownload').hidden,true, 'Reopening must not leave a stale download link');
  run('show(0)');
  assert.match(get('bookbackupstate').textContent,/No changes since reopening/, 'Selecting a page is not an edit');
  run("book[0].caption='Edited caption'; show(0)");
  assert.match(get('bookbackupstate').textContent,/Changes since reopening/);
  run("book[0].caption='Two cats in a kitchen'; show(0)");
  assert.match(get('bookbackupstate').textContent,/No changes since reopening/, 'Reverting an edit returns to the checkpoint');
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

  const copy = run("strengthenedPage(book[0], 'stronger-pixels', 'gentle')");
  context.strengthenedCopy=copy;
  assert.equal(copy.generation.level,'medium', 'Line treatment preserves the generated audience');
  assert.equal(copy.original_image,'raw-pixels');
  assert.equal(copy.line_treatment.mode,'gentle');
  run('book.push(strengthenedCopy); show(book.length - 1)');
  assert.match(get('generationinfo').textContent,/Teens.*lines strengthened.*scene complexity unchanged/);
  get('savebook').onclick();
  const treatedBook=JSON.parse(await savedBlob.text());
  get('loadfile').files=[{name:'treated.json',text:JSON.stringify(treatedBook)}];
  await get('loadfile').onchange();
  assert.equal(run('book[book.length - 1].generation.level'),'medium');
  assert.equal(run('book[book.length - 1].line_treatment.mode'),'gentle');
  assert.equal(run('book[book.length - 1].image'),'stronger-pixels');

  get('loadfile').files=[{text:JSON.stringify({version:3,pages:[{kind:'art',image:'legacy',caption:'Original artwork'},{kind:'story',body:'Original story'}]})}];
  await get('loadfile').onchange();
  assert.equal(run('book.length'),2);
  assert.equal(run('book[0].image'),'legacy');
  assert.equal(run('book[1].body'),'Original story');
  assert.equal(get('generationdetails').hidden,true);
  assert.equal(run('styleReference'),null);
  assert.equal(get('thumbs').children.length,2);
  assert.equal(get('thumbs').children[0]['aria-label'],'Show page 1: Artwork');
  get('pagestage').scrollTop=700;
  get('thumbs').children[0].onclick();
  assert.equal(run('current'),0);
  assert.equal(get('plate').src,'data:image/png;base64,legacy');
  assert.equal(get('pagestage').scrollTop,0);
  assert.equal(get('selectedpage').textContent,'Page 1 of 2 · Artwork');
  assert.equal(get('thumbs').children[0]['aria-current'],'page');
  assert.equal(get('thumbs').children[1]['aria-current'],undefined);
  assert.match(get('bookbackupstate').textContent,/No changes since reopening/);
  get('enlargeimage').onclick();
  assert.equal(get('imageviewer').hidden,false);
  assert.equal(get('viewerimage').src,'data:image/png;base64,legacy');
  assert.equal(get('viewertitle').textContent,'Page 1 of 2 — enlarged');
  assert.equal(document.activeElement,get('viewerclose'));
  get('viewerin').onclick();
  assert.equal(get('viewerzoom').textContent,'150%');
  assert.equal(get('viewerpicture').style.width,'150%');
  run('setImageViewerZoom(99)');
  assert.equal(get('viewerzoom').textContent,'400%');
  assert.equal(get('viewerin').disabled,true);
  get('viewerfit').onclick();
  assert.equal(get('viewerzoom').textContent,'Fit');
  assert.equal(get('viewerout').disabled,true);
  handlers.keydown({key:'Tab',preventDefault(){}});
  assert.equal(document.activeElement,get('viewerspace'));
  handlers.keydown({key:'Escape',preventDefault(){}});
  assert.equal(get('imageviewer').hidden,true);
  assert.equal(get('viewerimage').src,undefined);
  assert.equal(document.activeElement,get('enlargeimage'));
  assert.match(get('bookbackupstate').textContent,/No changes since reopening/);
  context.window.matchMedia=()=>({matches:true});
  get('thumbs').children[1].onclick();
  assert.equal(get('storyview').hidden,false);
  assert.equal(get('sheet').hidden,true);
  assert.equal(get('studiocanvas').scrollCalls,1);
  assert.equal(get('thumbs').children[1]['aria-current'],'page');
  assert.equal(get('thumbs').children[0]['aria-current'],undefined);
  context.URL.createObjectURL=()=>{throw new Error('download unavailable')};
  get('savebook').onclick();
  assert.match(get('booksavestatus').textContent,/pages are still in this tab/);
  assert.equal(run('book.length'),2, 'A failed download must not remove pages');

  // Transactional storage double: commit both stores together, or neither on abort.
  const db = {books:new Map(),documents:new Map(),assets:new Map(),fail:false,
    transaction(names,mode) {
      const pending=[]; let aborted=false;
      const tx={error:null, abort(){aborted=true;setImmediate(()=>tx.onabort?.());}, objectStore(name){
        return {get(id){const request={};queueMicrotask(()=>{request.result=structuredClone(db[name].get(id));request.onsuccess?.();});return request;},
          getAll(){const request={};queueMicrotask(()=>{request.result=structuredClone([...db[name].values()]);request.onsuccess?.();});return request;},
          put(value){pending.push([name,structuredClone(value)]);}};
      }};
      if(mode==='readwrite') setImmediate(()=>{
        if(aborted)return;
        if(db.fail){tx.error=new Error('quota');tx.onabort?.();return;}
        for(const [name,value] of pending)db[name].set(value.id,value);
        tx.oncomplete?.();
      });
      return tx;
    }};
  context.creationTestDb=db; context.persistenceDoc=treatedBook;
  run("creationsDb=creationTestDb; creationsReady=true; restoringCreation=true; restoreBookDocument(persistenceDoc); resetCreationIdentity('Unicorn collection'); restoringCreation=false; show(0)");
  assert.equal(await run('flushCreationSave()'),true);
  const firstId=run('creationId');
  assert.equal(db.books.size,1);
  assert.equal(db.books.get(firstId).name,'Unicorn collection');
  assert.equal(db.documents.get(firstId).data.pages[0].original_image,'raw-pixels');
  assert.equal(db.documents.get(firstId).data.pages[0].generation.prompt,'FULL PROMPT');
  assert.equal(JSON.stringify(db.documents.get(firstId)).includes('test-only-key'),false);
  assert.match(get('creationstatus').textContent,/Saved in My Creations/);
  const firstRevision=db.books.get(firstId).revision;
  run('selectBookPage(1)'); await run('flushCreationSave()');
  assert.equal(db.books.get(firstId).revision,firstRevision,'Selecting a thumbnail does not rewrite storage');
  run("book[0].caption='A revised saved prompt'; refreshBookState()");
  await run('flushCreationSave()');
  assert.equal(db.documents.get(firstId).data.pages[0].caption,'A revised saved prompt');
  await get('newcreation').onclick();
  assert.equal(run('book.length'),0);
  assert.equal(db.books.size,1,'New book retains existing collection');
  await run('showCreations()');
  assert.equal(get('creationgrid').children.length,1);
  get('creationsearch').value='missing';get('creationsearch').oninput();
  assert.equal(get('creationgrid').children.length,0);
  await run(`openCreation('${firstId}')`);
  assert.equal(run('book[0].caption'),'A revised saved prompt');
  assert.equal(run('book[0].original_image'),'raw-pixels');
  assert.equal(run('book[book.length - 1].line_treatment.mode'),'gentle');
  assert.match(get('creationstatus').textContent,/Reopened/);
  db.fail=true;
  run("book[0].caption='Unsaved change';refreshBookState()");
  assert.equal(await run('flushCreationSave()'),false);
  assert.match(get('creationstatus').textContent,/could not finish saving/);
  assert.equal(db.documents.get(firstId).data.pages[0].caption,'A revised saved prompt');
  await get('newcreation').onclick();
  assert.equal(run('book[0].caption'),'Unsaved change','Storage failure must prevent switching away');
  db.fail=false;
  // A newer revision in another tab must never be silently overwritten.
  db.books.get(firstId).revision+=1;
  assert.equal(await run('flushCreationSave()'),true);
  assert.equal(db.books.size,2);
  assert.notEqual(run('creationId'),firstId);
  assert.equal(db.documents.get(firstId).data.pages[0].caption,'A revised saved prompt');
  assert.match(get('creationstatus').textContent,/separate copy/);

  // Images and repeated reference strings are stored once; renaming does not rewrite artwork.
  context.largeImage='x'.repeat(100000);
  run("book.push({kind:'art',image:largeImage,original_image:largeImage,generation:{prompt:'large test',references:{style:{image:largeImage}}}});show(book.length-1)");
  await run('flushCreationSave()');
  const assetId=run('creationId'), assetCount=db.assets.size;
  assert.equal(assetCount,1);
  const compactDoc=db.documents.get(assetId);
  assert.equal(compactDoc.storage_format,'assets-v1');
  assert.ok(JSON.stringify(compactDoc).length<30000);
  get('creationname').value='Renamed large book';
  await run('flushCreationSave()');
  assert.equal(db.documents.get(assetId),compactDoc,'Rename must not rewrite the image manifest');
  assert.equal(db.assets.size,assetCount);
  await run(`openCreation('${assetId}')`);
  assert.equal(run('book[book.length-1].image'),context.largeImage);
  assert.equal(run('book[book.length-1].generation.references.style.image'),context.largeImage);
  run("book[book.length-1].caption='Changed caption only'");
  await run('flushCreationSave()');
  assert.equal(db.assets.size,assetCount,'Caption changes must reuse stored images');
  get('key').value='test-only-key';run('acknowledgeApiKey()');
  assert.match(get('keystatus').textContent,/Key ready in this tab/);
  assert.equal(JSON.stringify(run('bookDocument()')).includes('test-only-key'),false);
  get('keyforget').onclick();assert.equal(get('key').value,'');
  // Storage requests time out instead of leaving gallery controls waiting forever.
  const originalTimer=context.setTimeout;let timeoutCallback;
  context.setTimeout=fn=>{timeoutCallback=fn;return 1;};
  const pending=run('requestResult({})');timeoutCallback();
  await assert.rejects(pending,/did not respond in time/);
  context.setTimeout=originalTimer;
  console.log('PASS: deduplicated artwork, metadata-only renames, hydrated originals/references, password-manager key isolation and storage timeout');

  console.log('PASS: My Creations saves, prompts/originals, gallery/search/reopen, failure recovery and multi-tab conflict preservation');

  console.log('PASS: single/batch generation, reference snapshots, key exclusion, save/load, settings reuse, and legacy books');
})().catch(error=>{console.error(error);process.exitCode=1});
