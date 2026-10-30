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
  remove() {} getClientRects() { return this.hidden ? [] : [{}]; }
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
  readAsDataURL(file) { this.result = file.data; return this.onload(); }
}
class FakeImage {
  constructor() { this.naturalWidth=1024; this.naturalHeight=1536; }
  set src(value) { if (this.onload) this.onload(); }
}
const context = vm.createContext({document, Blob, FileReader:Reader, Image:FakeImage, AbortController, TextEncoder,
  window:{crypto:require('node:crypto').webcrypto,matchMedia:()=>({matches:false}),addEventListener(){}}, confirm:()=>true,
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
get('importbookbackup').onclick();
assert.equal(get('loadfile').clickCount,1, 'Import book backup opens the file picker directly');

(async()=>{
  // Hold a paid request open and attempt every other entry point.
  const initialFetch = context.fetch;
  let finishRequest, paidCalls=0;
  context.fetch=async()=>{paidCalls++;return new Promise(resolve=>{finishRequest=resolve;});};
  get('subject').value='Reliability test'; get('batchlist').value='Scene one\nScene two';
  const inFlight = get('compose').onclick();
  assert.equal(run('busy'),true);
  for(const id of ['compose','batchstart','cartgen','editapply']) {
    assert.equal(get(id).disabled,true);
    await get(id).onclick();
  }
  assert.equal(paidCalls,1,'Only the initial request reaches the provider');
  finishRequest({ok:false,json:async()=>({error:'Test provider unavailable'})});
  await inFlight;
  assert.match(get('status').textContent,/Test provider unavailable/);
  assert.equal(run('busy'),false);
  for(const id of ['compose','batchstart','cartgen','editapply']) assert.equal(get(id).disabled,false);
  assert.equal(run('book.length'),0);
  context.fetch=async()=>{paidCalls++;throw new Error('Test connection lost');};
  await get('batchstart').onclick();
  assert.equal(paidCalls,2,'Failed batch stops before requesting its second scene');
  assert.match(get('batchstatus').textContent,/1 failed.*1 skipped/);
  assert.equal(run('busy'),false);assert.equal(run('batchRunning'),false);
  assert.equal(get('batchstop').hidden,true);
  context.fetch=async()=>{const error=new Error('aborted');error.name='AbortError';throw error;};
  await get('compose').onclick();
  assert.match(get('status').textContent,/timed out.*check API usage/);
  assert.equal(run('busy'),false);
  context.fetch=async()=>({ok:true,json:async()=>{throw new Error('Bad JSON');}});
  await get('compose').onclick();
  assert.match(get('status').textContent,/unreadable response/);
  assert.equal(run('busy'),false);
  context.fetch=initialFetch;
  console.log('PASS: shared generation lock, failed-batch stop, timeout guidance and malformed-response recovery');
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
  const db = {books:new Map(),documents:new Map(),assets:new Map(),favorites:new Map(),fail:false,
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
  get('showfavorites').onclick();
  get('creationsearch').value='old favorite search';
  await get('quickloadbook').onclick();
  assert.equal(get('creationsmodal').hidden,false,'Open my books opens the internal bookshelf');
  assert.equal(run('creationGalleryMode'),'books','Open my books always shows books, even after browsing favorites');
  assert.equal(get('creationsearch').value,'');
  assert.equal(get('creationgrid').children.length,1);
  assert.equal(get('loadfile').clickCount,1,'Opening My Books must not launch the file picker');
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

  // Individual favorites are isolated documents; legacy book rows remain books.
  run("show(0)");
  const originalBookLength=run('book.length'), originalBookId=run('creationId');
  const storedBooksBefore=[...db.books.values()].filter(b=>b.kind!=='favorite').length;
  await get('savefavorite').onclick();
  assert.match(get('favoritestatus').textContent,/Saved to My Favorites Gallery/);
  assert.equal(run('book.length'),originalBookLength);
  assert.equal(run('creationId'),originalBookId);
  const favoriteMeta=[...db.favorites.values()].find(b=>b.kind==='favorite');
  assert.ok(favoriteMeta);
  context.favoriteId=favoriteMeta.id;
  const favorite=await run("readCreation(favoriteId,'favorites')");
  assert.equal(favorite.data.pages.length,1);
  assert.equal(favorite.data.pages[0].original_image,'raw-pixels');
  assert.equal(favorite.data.pages[0].generation.prompt,'FULL PROMPT');
  assert.equal(favorite.data.pages[0].generation.references.style.image,'style-pixels');
  assert.equal(JSON.stringify(favorite.data).includes('test-only-key'),false);
  assert.equal(favorite.data.favorite.sourceBook,'Renamed large book');
  await get('savefavorite').onclick();
  assert.match(get('favoritestatus').textContent,/Already saved/);
  assert.equal(db.favorites.size,1);

  // Failed saves never create a metadata-only favorite or claim success.
  db.fail=true;
  run("book[0].caption='New unsaved favorite'");
  await get('savefavorite').onclick();
  assert.match(get('favoritestatus').textContent,/Could not save/);
  assert.equal(db.favorites.size,1);
  db.fail=false;
  run("book[0].caption='Changed in the book only'");
  assert.notEqual((await run("readCreation(favoriteId,'favorites')")).data.pages[0].caption,run('book[0].caption'));
  get('creationsearch').value='';
  await run('showCreations()');
  assert.equal(get('creationgrid').children.length,storedBooksBefore);
  get('showfavorites').onclick();
  assert.equal(get('creationgrid').children.length,1);
  assert.equal(get('favoriteimportlabel').hidden,false);
  get('creationsearch').value='not in this gallery'; get('creationsearch').oninput();
  assert.equal(get('creationgrid').children.length,0);
  get('creationsearch').value=''; get('creationsearch').oninput();
  const card=get('creationgrid').children[0];
  const details=card.children.find(c=>c.tag==='details'); details.open=true; await details.ontoggle();
  assert.ok(details.children.some(c=>c.textContent==='FULL PROMPT'));

  // Colored companions append without replacing the outline or original.
  context.colorFile={name:'Unicorn color.png',type:'image/png',size:30,data:'data:image/png;base64,colored-pixels'};
  await run('attachFavoriteColor(favoriteId,colorFile)');
  let withColor=await run("readCreation(favoriteId,'favorites')");
  assert.equal(withColor.data.pages[0].image,favorite.data.pages[0].image);
  assert.equal(withColor.data.pages[0].original_image,'raw-pixels');
  assert.equal(withColor.data.favorite.coloredVersions[0].image,'colored-pixels');
  await run('attachFavoriteColor(favoriteId,colorFile)');
  assert.equal((await run("readCreation(favoriteId,'favorites')")).data.favorite.coloredVersions.length,1);
  db.fail=true;
  context.colorFile={...context.colorFile,data:'data:image/png;base64,second-color'};
  await run('attachFavoriteColor(favoriteId,colorFile)');
  assert.match(get('creationsmessage').textContent,/Could not save/);
  assert.equal((await run("readCreation(favoriteId,'favorites')")).data.favorite.coloredVersions.length,1);
  db.fail=false;

  // Favorite backup includes companion pixels and can restore into an empty gallery.
  context.URL.createObjectURL=b=>{savedBlob=b;return 'blob:test'};
  await run("favoriteAction(favoriteId,'backup')");
  const favoriteBackup=JSON.parse(await savedBlob.text());
  assert.equal(favoriteBackup.favorite.coloredVersions[0].image,'colored-pixels');
  assert.equal(favoriteBackup.pages[0].generation.prompt,'FULL PROMPT');
  assert.equal(JSON.stringify(favoriteBackup).includes('test-only-key'),false);
  db.favorites.delete(favoriteMeta.id);db.documents.delete(favoriteMeta.id);
  get('favoriteimport').files=[{size:100,text:JSON.stringify(favoriteBackup)}];
  await get('favoriteimport').onchange({target:get('favoriteimport')});
  assert.match(get('creationsmessage').textContent,/Favorite restored/);
  withColor=await run("readCreation(favoriteId,'favorites')");
  assert.equal(withColor.data.favorite.coloredVersions[0].image,'colored-pixels');
  assert.equal(run('creationId'),originalBookId);
  await get('favoriteimport').onchange({target:get('favoriteimport')});
  assert.match(get('creationsmessage').textContent,/already exists/);

  // Add a detached copy; keep the active book, its existing pages, and favorite intact.
  await run("favoriteAction(favoriteId,'add')");
  assert.equal(run('creationId'),originalBookId);
  assert.equal(run('book.length'),originalBookLength+1);
  assert.equal(run('book[book.length-1].original_image'),'raw-pixels');
  assert.equal(run('book[book.length-1].generation.prompt'),'FULL PROMPT');
  run("book[book.length-1].generation.prompt='Edited copy'");
  assert.equal((await run("readCreation(favoriteId,'favorites')")).data.pages[0].generation.prompt,'FULL PROMPT');
  assert.equal([...db.books.values()].filter(b=>b.kind!=='favorite').length,storedBooksBefore);
  get('savefavorite').hidden=false;run('show(-1)');assert.equal(get('savefavorite').hidden,true);

  // An older favorite revision cannot overwrite a colored companion from another tab.
  const colorBefore=JSON.stringify(db.documents.get(favoriteMeta.id));
  context.staleFavoriteMeta={...db.favorites.get(favoriteMeta.id)};
  db.favorites.get(favoriteMeta.id).revision+=1;
  await assert.rejects(run('writeCreation(staleFavoriteMeta,prepareCreationDocument({pages:[]}),staleFavoriteMeta.revision)'),/another tab/);
  assert.equal(JSON.stringify(db.documents.get(favoriteMeta.id)),colorBefore);
  get('favoriteimport').files=[{size:30,text:'{"pages":[]}'}];
  await get('favoriteimport').onchange({target:get('favoriteimport')});
  assert.match(get('creationsmessage').textContent,/Could not restore/);
  assert.equal(run('book.length'),originalBookLength+1);

  // Inspect the actual database version, then add only missing stores.
  const existingStores=new Set(['books','documents','assets']), addedStores=[];
  db.version=2;db.close=()=>{};
  db.objectStoreNames={contains:name=>existingStores.has(name)};
  db.createObjectStore=(name,options)=>{assert.equal(options.keyPath,'id');addedStores.push(name);existingStores.add(name);};
  const versions=[];
  context.window.indexedDB={open(name,version){
    assert.equal(name,'fusion-coloring-creations');versions.push(version);
    const request={result:db};queueMicrotask(()=>{if(version!==undefined){db.version=version;request.onupgradeneeded();}request.onsuccess();});return request;
  }};
  run('creationsReady=false;creationsDb=null');
  assert.equal(await run('initCreations()'),true);
  assert.deepEqual(versions,[undefined,3]);
  assert.deepEqual(addedStores,['favorites']);
  assert.equal(db.books.size,storedBooksBefore);
  assert.equal(db.favorites.size,1);

  // A newer existing database is opened without a hard-coded downgrade request.
  db.version=9;versions.length=0;
  run('creationsReady=false;creationsDb=null');
  assert.equal(await run('initCreations()'),true);
  assert.deepEqual(versions,[undefined]);
  assert.equal(db.version,9);

  // Startup failure is recoverable with Save now; never ask to switch books or reload.
  let openFailure=true, openCalls=0, confirmCalls=0;
  run("book[book.length-1].caption='Pending while storage is disconnected'");
  context.confirm=()=>{confirmCalls++;return false;};
  context.window.indexedDB={open(name,version){
    assert.equal(version,undefined);openCalls++;
    const request={result:db,error:Object.assign(new Error('Connection lost'),{name:'UnknownError'})};
    queueMicrotask(()=>openFailure?request.onerror():request.onsuccess());return request;
  }};
  run('creationsReady=false;creationsDb=null');
  assert.equal(await run('initCreations()'),false);
  assert.match(get('creationstatus').textContent,/UnknownError.*Connection lost/);
  await get('savecreation').onclick();
  assert.equal(confirmCalls,0,'Save now must not show a switch-book confirmation');
  assert.equal(run('book.length'),originalBookLength+1);
  openFailure=false;
  await get('savecreation').onclick();
  assert.equal(run('creationsReady'),true);
  assert.equal(run('creationId'),originalBookId);
  assert.match(get('creationstatus').textContent,/Saved in My Creations/);
  assert.equal(db.books.size,storedBooksBefore);

  // Failed gallery reads stay errors, even after a search or tab change.
  openFailure=true;run('creationsReady=false;creationsDb=null');
  await run('showCreations()');
  assert.match(get('creationsmessage').textContent,/Could not read My Books/);
  get('creationsearch').value='fusion';get('creationsearch').oninput();
  get('showbooks').onclick();
  assert.match(get('creationsmessage').textContent,/UnknownError.*Connection lost/);
  assert.doesNotMatch(get('creationsmessage').textContent,/No saved books|No matches/);
  assert.equal(get('retrystorage').hidden,false);
  openFailure=false;
  await get('retrystorage').onclick();
  assert.equal(get('creationgrid').children.length,storedBooksBefore);
  assert.equal(get('retrystorage').hidden,true);
  const callsBeforeClose=openCalls;
  db.onclose();
  assert.equal(run('creationsReady'),false);
  await get('savecreation').onclick();
  assert.equal(openCalls,callsBeforeClose+1);
  assert.equal(run('creationsReady'),true);

  // A timed-out open closes late connections so retries cannot block upgrades.
  const savedTimer=context.setTimeout;
  let connectionTimeout, lateRequest, lateClosed=0;
  context.setTimeout=fn=>{connectionTimeout=fn;return 1;};
  context.window.indexedDB={open(){lateRequest={result:{close(){lateClosed++;}}};return lateRequest;}};
  const opening=run('openCreationsDatabase()');
  lateRequest.onblocked();connectionTimeout();
  await assert.rejects(opening,/Browser storage did not respond/);
  lateRequest.onsuccess();assert.equal(lateClosed,1);
  context.setTimeout=savedTimer;
  // Complete sharing export skips KDP preflight and preserves the arranged book.
  get('ctitle').value='Unicorns and Fantasy';get('csubtitle').value='For my friends';
  get('cauthor').value='Christine';get('cblurb').value='Enjoy coloring!';get('ccolor').value='#254AA6';
  run("setCoverArt('front-color-pixels');setBackCover('back-color-pixels')");
  const coverDoc=run('bookDocument()');
  assert.equal(coverDoc.cover.front_image,'front-color-pixels');
  assert.equal(coverDoc.cover.back_image,'back-color-pixels');
  context.roundTripCover=JSON.parse(JSON.stringify(coverDoc));
  run("loadCoverData(null)");assert.equal(get('ctitle').value,'');
  run('restoreBookDocument(roundTripCover)');
  assert.equal(get('ctitle').value,'Unicorns and Fantasy');
  assert.equal(run('coverArt.image'),'front-color-pixels');
  assert.equal(run('backCoverImage'),'back-color-pixels');
  const snapshot=JSON.stringify(run('bookDocument()')), exportRequests=[];
  context.fetch=async(url,options)=>{
    exportRequests.push({url,payload:JSON.parse(options.body)});
    return {ok:true,blob:async()=>new Blob(['%PDF-test'],{type:'application/pdf'})};
  };
  await get('completebook').onclick();
  assert.equal(exportRequests.length,1);
  assert.equal(exportRequests[0].url,'/complete-book');
  assert.equal(exportRequests[0].payload.pages.length,run('book.length'));
  assert.equal(exportRequests[0].payload.cover.back_image,'back-color-pixels');
  assert.equal(JSON.stringify(exportRequests).includes('test-only-key'),false);
  assert.match(get('completestatus').textContent,/Complete book downloaded: front cover/);
  assert.equal(document.body.children.at(-1).download,'Unicorns-and-Fantasy-complete.pdf');
  assert.equal(JSON.stringify(run('bookDocument()')),snapshot);
  context.fetch=async()=>({ok:false,json:async()=>({error:'Unreadable cover image'})});
  await get('completebook').onclick();
  assert.match(get('completestatus').textContent,/Unreadable cover image.*unchanged/);
  assert.equal(get('completebook').disabled,false);
  assert.equal(JSON.stringify(run('bookDocument()')),snapshot);
  run('loadCoverData(null)');
  assert.equal(run('coverArt.image'),null);assert.equal(run('backCoverImage'),null);
  await get('completebook').onclick();
  assert.match(get('completestatus').textContent,/Enter your book title/);
  console.log('PASS: complete-book export without KDP, cover round-trip, legacy resets, key exclusion and unchanged artwork on export failures');
  console.log('PASS: version-safe storage, missing-store upgrade, startup retry, Save now without confirmation, persistent gallery errors, reconnect and late-connection cleanup');
  console.log('PASS: favorite isolation, duplicate saves, failure recovery, book/favorite filtering, prompt details, colored companions, backup restore and reuse');
  console.log('PASS: deduplicated artwork, metadata-only renames, hydrated originals/references, password-manager key isolation and storage timeout');

  console.log('PASS: My Creations saves, prompts/originals, gallery/search/reopen, failure recovery and multi-tab conflict preservation');

  console.log('PASS: single/batch generation, reference snapshots, key exclusion, save/load, settings reuse, and legacy books');
})().catch(error=>{console.error(error);process.exitCode=1});
