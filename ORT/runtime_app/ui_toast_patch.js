window.ortEnsureToast = function(){
  let el = document.getElementById('ort-start-toast');
  if (el) return el;
  el = document.createElement('div');
  el.id = 'ort-start-toast';
  el.style.cssText = 'display:none;position:fixed;top:18px;right:18px;z-index:99999;background:rgba(10,20,46,.96);color:white;padding:14px 16px;border-radius:16px;border:1px solid rgba(125,211,252,.35);box-shadow:0 10px 25px rgba(0,0,0,.35);min-width:260px';
  el.innerHTML = '<div style="display:flex;align-items:center;gap:10px"><div class="ort-spin" style="width:18px;height:18px;border:3px solid rgba(255,255,255,.22);border-top-color:#7dd3fc;border-radius:999px;animation:ortspin .9s linear infinite"></div><div><div style="font-weight:700">Sedang Memuat ORTCore...</div><div style="font-size:12px;color:#cbd5e1">Mohon tunggu, engine sedang disiapkan.</div></div></div>';
  document.body.appendChild(el);
  let style = document.createElement('style');
  style.innerHTML='@keyframes ortspin{to{transform:rotate(360deg)}}';
  document.head.appendChild(style);
  return el;
}
window.ortShowStartToast = function(){ window.ortEnsureToast().style.display='block'; }
window.ortHideStartToast = function(){ let el=document.getElementById('ort-start-toast'); if(el) el.style.display='none'; }
