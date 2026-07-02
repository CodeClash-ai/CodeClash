const DB=false;

function robot(state, unit) { 
  //console.log("Hello World!");
  
  function getObj(x,y){
    return state.objByCoords(new Coords(x,y));
  }
  
  //console.log(getObj(1,3)); 
  
  function run(dir){
    if(DB){debug.log("trying",dir);}
    let D=dir;
    if(DB){debug.log("has",getObj(unit.coords.x+D.toCoords.y,unit.coords.y+D.toCoords.y));}
    if(!getObj(unit.coords.x+D.toCoords.x,unit.coords.y+D.toCoords.y)){
      if(DB){debug.log(""+D,getObj(unit.coords.x+D.toCoords.x,unit.coords.y+D.toCoords.y));}
      return Action.move(dir);
    }
    D=dir.rotateCw;
    if(!getObj(unit.coords.x+D.toCoords.x,unit.coords.y+D.toCoords.y)){
      if(DB){debug.log(""+D,getObj(unit.coords.x+D.toCoords.x,unit.coords.y+D.toCoords.y));}
      return Action.move(D);
    }
    D=dir.rotateCcw;
    if(!getObj(unit.coords.x+D.toCoords.x,unit.coords.y+D.toCoords.y)){
      if(DB){debug.log(""+D,getObj(unit.coords.x+D.toCoords.x,unit.coords.y+D.toCoords.y));}
      return Action.move(D);
    }
    return Action.move(dir);
  }
  
  function flee(dir){
    if(DB){debug.log("trying",dir);}
    let D=dir;
    if(DB){debug.log("has",getObj(unit.coords.x+D.toCoords.y,unit.coords.y+D.toCoords.x));}
    if(!getObj(unit.coords.x+D.toCoords.x,unit.coords.y+D.toCoords.y)){
      if(DB){debug.log(""+D,getObj(unit.coords.x+D.toCoords.x,unit.coords.y+D.toCoords.y));}
      return Action.move(dir);
    }
    D=dir.rotateCw;
    if(!getObj(unit.coords.x+D.toCoords.x,unit.coords.y+D.toCoords.y)){
      if(DB){debug.log(""+D,getObj(unit.coords.x+D.toCoords.x,unit.coords.y+D.toCoords.y));}
      return Action.move(D);
    }
    D=dir.rotateCcw;
    if(!getObj(unit.coords.x+D.toCoords.x,unit.coords.y+D.toCoords.y)){
      if(DB){debug.log(""+D,getObj(unit.coords.x+D.toCoords.x,unit.coords.y+D.toCoords.y));}
      return Action.move(D);
    }
    return Action.attack(dir.opposite);
  }
  
  let enemies = state.objsByTeam(state.otherTeam)
  if(enemies){
    let closestEnemy = _.minBy(enemies,
      e => e.coords.distanceTo(unit.coords) + e.health/10
    )
    let direction = unit.coords.directionTo(closestEnemy.coords);

    if(unit.health<2){
      if(DB){debug.log("tas","flee");}
      if(closestEnemy.health<unit.health){
        return Action.attack(direction);
      }
      return flee(direction.opposite);
    }

    if(unit.coords.distanceTo(closestEnemy.coords) < 3) {
      let closeGuys=0;
      for(let i=-2;i<3;i++){
        for(let j=-2;j<3;j++){
          let obj=getObj(closestEnemy.coords.x+i,closestEnemy.coords.y+j);
          if(obj&&obj.team==unit.team){
            closeGuys++;
          }
        }
      }
      if(closeGuys<2){
        if(DB){debug.log("tas","flee");}
        return run(direction.opposite);
      }
      if(unit.coords.distanceTo(closestEnemy.coords) === 1) {
        return Action.attack(direction);
      } else {
        if(DB){debug.log("task","attack");}
        return run(direction);
      }
    }
    let friends = state.objsByTeam(state.ourTeam);

    let closestFriend = _.minBy(friends,
      f =>{
        let nearbyEnemey=false;

        let enemies = state.objsByTeam(state.otherTeam)
        let closestEnemy = _.minBy(enemies,
          e => e.coords.distanceTo(f.coords) + e.health/10
        )
        if(f.coords.distanceTo(closestEnemy.coords)>2){
          return Infinity;
        }
        return f.coords.distanceTo(unit.coords);
      }
    )

    if(closestFriend){
      let enemies = state.objsByTeam(state.otherTeam)
      let closestEnemy = _.minBy(enemies,
        e => e.coords.distanceTo(closestFriend.coords) + e.health/10
      )

      if(closestFriend.coords.distanceTo(closestEnemy.coords)<3){
        if(DB){debug.log("task","friend");}
        return run(unit.coords.directionTo(closestEnemy.coords));
      }
    }
  }
  
  let to = unit.coords.directionTo(new Coords(10,10));
  let inward = getObj(unit.coords.x+to.toCoords.x,unit.coords.y+to.toCoords.y);
  
  if(!getObj(unit.coords.x+to.opposite.toCoords.x,unit.coords.y+to.opposite.toCoords.y)){
    if(DB){debug.log("task","out");}
    return run(unit.coords.directionTo(new Coords(10,10)).opposite);
  }

  if(!inward){
    return Action.attack(to);
  }
  if(DB){debug.log("task","do nothing");}
  return null;
}

