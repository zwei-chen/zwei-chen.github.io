const select=document.querySelector('#theme-select');
const media=matchMedia('(prefers-color-scheme: dark)');
let preference='system';
try {preference=localStorage.getItem('dive-theme')||'system';} catch {}
if(!['system','light','dark'].includes(preference))preference='system';
select.value=preference;
function applyTheme(){
  const theme=preference==='system'?(media.matches?'dark':'light'):preference;
  document.documentElement.dataset.theme=theme;
  document.querySelector('meta[name="theme-color"]').content=theme==='dark'?'#0d1824':'#f4f8fc';
  dispatchEvent(new CustomEvent('themechange'));
}
select.addEventListener('change',()=>{preference=select.value;try{localStorage.setItem('dive-theme',preference);}catch{}applyTheme();});
media.addEventListener('change',applyTheme);applyTheme();
