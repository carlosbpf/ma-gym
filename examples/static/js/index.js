const canvas = document.querySelector('canvas')
const c = canvas.getContext('2d')
var socket = io();
let pathName = document.location.pathname;
let userID = pathName.substring(pathName.lastIndexOf('/')+1,pathName.length);
let roomID = pathName.replace('/'+userID,'').replace('/', '');

let currentRoundInfo = {index: null, start: null, destination : null, color:'',}
// Event Listeners
canvas.addEventListener("keydown", (event) => {
if (event.isComposing || event.keyCode === 229) {
 return;
}
handleKeyStroke(event);
});
document.querySelector("canvas").onblur = function() {
    let me = this;
    setTimeout(function() {
        me.focus();
    }, 500);
}
addEventListener('resize', () => {
  canvas.width = innerWidth
  canvas.height = innerHeight

  init()
})
function init() {
    canvas.focus();
    console.log('Initializing game ...');
    console.log('USER ID : ' + userID)
    console.log('ROOM ID: ' + roomID);
    socket.emit("join", {room_id: roomID});
}
const LEFT = 37;
const RIGHT = 39;
const UP = 38;
const Q_ = 81
const W_ = 87
const E_ = 69;
const SPACE = 32;
let DEFAULT_ACTION = 0;
function handleKeyStroke(event) {
    console.log(event.keyCode);
    let action = null;
    switch (event.keyCode) {
        case LEFT: {
            action = "left";
            break;
        }
        case RIGHT: {
            action = "right";
            break;
        }
        case UP: {
            action = "up";
            break;
        }
        case Q_: {
            action = "q";
            break;
        }
        case W_: {
            action = "w";
            break;
        }
        case E_: {
            action = "e";
            break;
        }
        case SPACE: {
            action = "space";
            break;
        }
        default:
            action = null;
    }
    if (action != null) {
        console.log(`Sending action: ${action}`)
        socket.emit("action", {action: action});
    }
}
let lastImageToDraw = null;
// Animation Loop

socket.on('game_board_update', function(data) {
  lastImageToDraw = new Image();
  lastImageToDraw.src = "data:image/png;base64,"+ data.state;

});
function discoverOrientation(val, route){
    //(1 - fwd, 2 - turn right, 3 - turn left)
    /*
    *
    * Agent index: 0 route Index 1 route translated (7, 13)
    * Agent index: 1 route Index 1 route translated (7, 13)
    * Agent index: 2 route Index 2 route translated (0, 7)
    * Agent index: 3 route Index 3 route translated (6, 0)
    *
    * */

    console.log(val +" - " + route);
    if(val == '0,6') {
        //return "N";
        if(route == "1") {return "S";}
        if(route == "2") {return "W";}
        if(route == "3") {return "E";}

    }
    if(val == '7,0') {
        //return "W";
        if(route == "1") {return "E";}
        if(route == "2") {return "S";}
        if(route == "3") {return "N";}

    }
    if(val == '6,13') {
        //return "E";
        if(route == "1") {return "W";}
        if(route == "2") {return "N";}
        if(route == "3") {return "S";}
    }
    if(val == '13,7') {
        //return "S";
        if(route == "1") {return "N";}
        if(route == "2") {return "E";}
        if(route == "3") {return "W";}
    }

}
function handleOnClick(){
     let element = document.getElementById("go_btn");
    element.classList.remove("goOnOff");
    element.classList.add("goOn");

    let element2 = document.getElementById("stop_btn");
    element2.classList.remove("breakOn");
    element2.classList.add("breakOnOff");
    DEFAULT_ACTION = 0;
    socket.emit("action", {action: DEFAULT_ACTION});
}
function handleBreakClick(){
     let element = document.getElementById("go_btn");
    element.classList.remove("goOn");
    element.classList.add("goOnOff");

    let element2 = document.getElementById("stop_btn");
    element2.classList.remove("breakOnOff");
    element2.classList.add("breakOn");
    DEFAULT_ACTION = 1;
    socket.emit("action", {action: DEFAULT_ACTION});

}
socket.on('game_setup',function(data){
    if(socket.id == data.socket_id) {
        currentRoundInfo = {index: data.index, origin: data.origin, route: data.route, color: data.color};
        document.getElementById('carColor').style.backgroundColor = currentRoundInfo.color;
        document.getElementById('carDestination').innerText = discoverOrientation(currentRoundInfo.origin, currentRoundInfo.route);
    }
});
socket.on('waiting_game',function(){
    document.getElementById('messageDisplay').style.display = 'block';
    document.getElementById('gameSetup').style.display = 'none';
});
socket.on('start_game_episode',function(){
    document.getElementById('messageDisplay').style.display = 'none';
    document.getElementById('gameSetup').style.display = 'block';
});

function animate() {
  requestAnimationFrame(animate)
  //c.clearRect(0, 0, canvas.width, canvas.height)
  if(lastImageToDraw != null) {
      c.drawImage(lastImageToDraw, 0, 0);
      lastImageToDraw = null;
  }
}
init();
animate();