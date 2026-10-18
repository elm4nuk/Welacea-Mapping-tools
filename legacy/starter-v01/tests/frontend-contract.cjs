const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { webcrypto } = require('node:crypto');
const nodes = new Map();
const stub = () => ({ addEventListener(){}, classList:{add(){},remove(){}}, textContent:'', innerHTML:'', value:'', close(){}, click(){}, setAttribute(){} });
const context = vm.createContext({ console, crypto:webcrypto, structuredClone, URL, Blob, setTimeout, clearTimeout, AbortSignal,
  document:{querySelector(s){if(!nodes.has(s))nodes.set(s,stub());return nodes.get(s);},addEventListener(){}},
  window:{addEventListener(){},print(){}}, Image:class {}, FileReader:class {} });
let src=fs.readFileSync(require('node:path').join(__dirname,'../dist/app.js'),'utf8');
src=src.replace(/init\(\);\s*$/, '');
vm.runInContext(src,context);
function run(s){return vm.runInContext(s,context);}
let passed=0;
function test(name,fn){fn();passed++;console.log('PASS',name);}
test('valid detection preserves normalized position and requires review',()=>{
  const x=run(`validateDetection({image_width:100,image_height:80,model:'test',detections:[{label:'plant',confidence:0.8,bbox:[0.1,0.2,0.3,0.4]}]},{width:100,height:80})[0]`);
  assert.equal(x.status,'pending');assert.equal(x.source,'ai');assert.equal(x.x,0.25);assert.equal(x.y,0.4);
});
test('wrong image dimensions are rejected',()=>assert.throws(()=>run(`validateDetection({image_width:99,image_height:80,detections:[]},{width:100,height:80})`),/Ukuran/));
test('boxes outside photo are rejected',()=>assert.throws(()=>run(`validateDetection({image_width:100,image_height:80,detections:[{label:'plant',confidence:.8,bbox:[.9,.2,.5,.1]}]},{width:100,height:80})`),/bbox/));
test('unknown labels and invalid confidence are rejected',()=>{
  assert.throws(()=>run(`validateDetection({image_width:100,image_height:80,detections:[{label:'person',confidence:.8,bbox:[.1,.2,.2,.1]}]},{width:100,height:80})`),/Label/);
  assert.throws(()=>run(`validateDetection({image_width:100,image_height:80,detections:[{label:'plant',confidence:NaN,bbox:[.1,.2,.2,.1]}]},{width:100,height:80})`),/confidence/);
});
test('unreviewed AI does not inflate plant count',()=>{
  assert.equal(run(`count({annotations:[{kind:'plant',status:'pending'},{kind:'plant',status:'confirmed'},{kind:'gap',status:'confirmed'}]},'plant')`),1);
});
test('manual demo counts are explicit and consistent',()=>{
  run(`state={surveys:[makeDemo()],settings:{apiUrl:''}};state.activeSurveyId=state.surveys[0].id;state.activePhotoId=state.surveys[0].photos[0].id;`);
  assert.equal(run(`count(activePhoto(),'plant')`),28);assert.equal(run(`count(activePhoto(),'gap')`),2);
  assert.equal(run(`activeSurvey().isDemo`),true);
});
test('all views render and example is labeled',()=>{
  for(const view of ['overview','surveyView','reportView','settingsView'])assert.ok(run(`${view}()`).length>100);
  assert.match(run(`overview()`),/bukan hasil AI/);
  assert.match(run(`reportView()`),/tidak boleh dijumlahkan/);
});
test('user text is escaped and spreadsheet formulas are neutralized',()=>{
  assert.equal(run(`esc('<script>"&')`),'&lt;script&gt;&quot;&amp;');
  assert.equal(run(`csvCell('=SUM(A1)')`),'"\'=SUM(A1)"');
  run(`activeSurvey().name='<img src=x onerror=alert(1)>';`);
  assert.ok(!run(`reportView()`).includes('<img src=x'));
});
test('empty survey renders actionable upload state',()=>{
  run(`state.surveys=[{id:'empty',name:'Uji',crop:'Jagung',date:'2026-10-18',location:'A',photos:[],isDemo:false}];state.activeSurveyId='empty';`);
  assert.match(run('overview()'),/Pilih foto/);assert.equal(run(`count(activePhoto(),'plant')`),0);
});
console.log(`${passed} frontend contract checks passed; these do not replace browser QA.`);
