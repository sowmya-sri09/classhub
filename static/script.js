// Global keyboard: Fake Teacher
document.addEventListener('keydown', e=>{
  if(e.ctrlKey && e.key.toLowerCase()==='q'){ window.location.href='/fake'; }
});

// Dashboard-only code
if (document.getElementById('attForm')) {
  const socket = io();

  // Attendance
  document.getElementById('attForm').addEventListener('submit', e=>{
    e.preventDefault();
    const formData = new FormData(e.target);
    fetch('/mark-attendance', {method:'POST', body: formData})
      .then(r=>r.json()).then(res=>{
        document.getElementById('attInfo').textContent = "Marked at "+res.ts+" (+5 pts)";
      });
  });

  // Chat join/send
  const msgs = document.getElementById('msgs');
  const roomSel = document.getElementById('room');
  const nick = document.getElementById('nickname').textContent;
  let currentRoom = 'main';
  let sendStyle = 'normal';

  function appendMsg(html){
    msgs.insertAdjacentHTML('beforeend', html);
    msgs.scrollTop = msgs.scrollHeight;
  }

  document.getElementById('joinBtn').onclick = ()=>{
    socket.emit('join', {room: roomSel.value, nickname: nick});
    currentRoom = roomSel.value;
    appendMsg(`<div><i>Joined ${currentRoom}</i></div>`);
  };

  document.getElementById('sendBtn').onclick = ()=>{
    const inp = document.getElementById('msgInput');
    if(!inp.value) return;
    socket.emit('send-msg', {room: currentRoom, nickname: nick, text: inp.value, style: sendStyle});
    inp.value = '';
    // reset invisible
    sendStyle = 'normal';
    document.getElementById('invisibleBtn').classList.remove('active');
  };

  socket.on('new-msg', d=>{
    const cls = d.style==='invisible' ? 'invisible-ink' : '';
    appendMsg(`<div><b>${d.nickname}:</b> <span class="${cls}">${d.text}</span> <small class="text-muted">${d.ts}</small></div>`);
  });
  socket.on('status', d=> appendMsg(`<div><i>${d.msg}</i></div>`));
  socket.on('reaction', d=> appendMsg(`<div><i>${d.nickname} reacted ${d.emoji}</i></div>`));
  socket.on('attendance-marked', d=> appendMsg(`<div><i>${d.nickname} marked attendance (+5)</i></div>`));
  socket.on('new-upload', d=> appendMsg(`<div><i>New upload by ${d.uploader}: ${d.filename}</i></div>`));
  socket.on('teams-result', d=> appendMsg(`<div><i>Teams: ${JSON.stringify(d.teams)}</i></div>`));

  // Fun buttons
  document.getElementById('truthBtn').onclick = ()=>{
    const list = ["Show your last meme","Sing 10 sec","Secret talent?","Tell a fun fact","Do 5 squats 😆"];
    appendMsg(`<div><b>Truth/Dare:</b> ${list[Math.floor(Math.random()*list.length)]}</div>`);
  };
  document.getElementById('emojiBtn').onclick = ()=> socket.emit('reaction', {nickname: nick, emoji: "😂"});
  document.getElementById('teamsBtn').onclick = ()=>{
    const names = prompt("Enter names comma-separated", nick) || nick;
    socket.emit('random-teams', {members: names.split(','), size: 2});
  };
  document.getElementById('invisibleBtn').onclick = (e)=>{
    sendStyle = (sendStyle==='normal' ? 'invisible' : 'normal');
    e.target.classList.toggle('active');
  };

  document.getElementById('fakeBtn').onclick = ()=> window.location.href='/fake';
}
