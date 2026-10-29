const runtimeURL = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/';
let handle;
async function initialize() {
  const {loadPyodide} = await import(`${runtimeURL}pyodide.mjs`);
  const pyodide = await loadPyodide({indexURL:runtimeURL});
  const response = await fetch(new URL('./planner.py',import.meta.url),{cache:'no-cache'});
  if (!response.ok) throw new Error('Cannot load planner.py');
  await pyodide.runPythonAsync(await response.text());
  handle=pyodide.globals.get('handle_json');
  self.postMessage({type:'ready'});
}
self.onmessage=({data})=>{
  if (!handle) return;
  try {self.postMessage({type:'result',id:data.id,...JSON.parse(handle(JSON.stringify(data.request)))});}
  catch(error) {console.error(error);self.postMessage({type:'result',id:data.id,ok:false,error:data.request.lang==='en'?'Calculation failed. Check the inputs or shorten the profile.':'计算未能完成，请检查输入或缩短计划。'});}
};
initialize().catch(error=>{console.error(error);self.postMessage({type:'fatal'});});
