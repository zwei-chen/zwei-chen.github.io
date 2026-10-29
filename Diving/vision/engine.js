import {lang,t} from './language.js';
export class PythonEngine {
  constructor(status,onReady,onFailure=()=>{}){this.status=status;this.onReady=onReady;this.onFailure=onFailure;this.pending=new Map();this.nextId=0;this.ready=false;}
  start(){
    this.worker?.terminate();clearTimeout(this.initTimer);this.ready=false;
    this.status.textContent=t('正在准备 Python 计算环境，首次加载需要一些时间…','Preparing Python. The first load may take a moment…');
    try {
      const worker=new Worker(new URL('./worker.mjs',import.meta.url),{type:'module'});this.worker=worker;
      worker.onerror=()=>{if(this.worker===worker)this.fail();};
      worker.onmessage=({data})=>{
        if(this.worker!==worker)return;
        if(data.type==='ready'){clearTimeout(this.initTimer);this.ready=true;this.status.textContent=t('计算环境已就绪。','Calculation engine ready.');this.onReady();}
        else if(data.type==='fatal')this.fail();
        else if(data.type==='result'){const task=this.pending.get(data.id);if(!task)return;clearTimeout(task.timer);this.pending.delete(data.id);data.ok?task.resolve(data.result):task.reject(new Error(data.error));}
      };
      this.initTimer=setTimeout(()=>this.fail(t('计算环境加载超时，请重试。','Engine loading timed out. Please retry.')),120000);
    }catch{this.fail();}
  }
  fail(message=t('计算环境加载失败，请检查网络后重试。','Engine failed to load. Check your connection and retry.')){
    clearTimeout(this.initTimer);this.worker?.terminate();this.ready=false;this.status.textContent=message;
    for(const task of this.pending.values()){clearTimeout(task.timer);task.reject(new Error(message));}this.pending.clear();this.onFailure();
  }
  call(action,payload){
    return new Promise((resolve,reject)=>{
      if(!this.ready)return reject(new Error(t('计算环境尚未就绪，请稍候。','The calculation engine is not ready yet.')));
      const id=++this.nextId,timer=setTimeout(()=>this.fail(t('计算超时，请简化输入并重试。','Calculation timed out. Simplify the inputs and retry.')),45000);
      this.pending.set(id,{resolve,reject,timer});this.worker.postMessage({id,request:{action,payload,lang}});
    });
  }
}
