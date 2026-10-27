'use strict';
// The preview uses the real dashboard document and its styles. Only its design
// comes from the editor's in-memory draft; no layout is written to the server.
if(window.KICKBASE_DASHBOARD?.preview){
  document.body.classList.add('dashboard-preview');
  document.querySelectorAll('.report-actions button').forEach(button=>button.disabled=true);
  document.addEventListener('click',event=>{if(event.target.closest('a'))event.preventDefault();});
  let resolve,received=false;
  const listeners=new Set(),ready=new Promise(done=>resolve=done);
  window.KANE_PREVIEW={ready,onChange:listener=>listeners.add(listener)};
  window.addEventListener('message',event=>{
    if(event.origin!==location.origin||event.source!==parent||parent===window||event.data?.type!=='kane-preview-design')return;
    const state=event.data.state;
    if(!state?.design||!['desktop','mobile'].includes(state.mode)||!state.design[state.mode])return;
    if(!received){received=true;resolve(state);}else listeners.forEach(listener=>listener(state));
  });
  const tellParent=message=>{if(parent!==window)parent.postMessage(message,location.origin);};
  tellParent({type:'kane-preview-ready'});
  const shell=document.querySelector('.app-shell');let lastHeight=0;
  new ResizeObserver(()=>{
    const height=Math.ceil(shell.getBoundingClientRect().height);
    if(height!==lastHeight){lastHeight=height;tellParent({type:'kane-preview-height',height});}
  }).observe(shell);
}
