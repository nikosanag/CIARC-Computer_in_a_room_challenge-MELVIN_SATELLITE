import math

SIMULATION = False
DEBUG_HERE = False




def calculate_velocity(melvin_x, melvin_y, target_x, target_y, vx_curr, vy_curr):

  def is_valid(vx, vy):
    return vx >= 3 and vx <= 71 and vy >= 3 and vy <= 71
  
  def needs_slight_change (vx, vy):
    return vx < 3.5 and vy < 3.5


  def find_naive_velocity(melvin_x, melvin_y, target_x, target_y, limitations):
    completed1 = False
    completed2 = False
    while not (completed1 and completed2):
      if target_x <= melvin_x:
        target_x += 21600
        completed1 = False
      else: completed1 = True
      if target_y <= melvin_y:
        target_y += 10800
        completed2 = False
      else: completed2 = True
    if melvin_y - target_y == 0 or melvin_x - target_x == 0:
      if DEBUG_HERE:
        print("ERROR: Something went terribly wrong with finding gradient!")
      return
    grad = (melvin_y - target_y) / (melvin_x - target_x)
    angle = math.atan(grad)
    velx = limitations['vabs'] * math.cos(angle)
    vely = limitations['vabs'] * math.sin(angle)
    if DEBUG_HERE:
      print (f"Found naive solutions for grad = {grad}:")
      print(f"vx = {velx}, vy = {vely}")
    return velx, vely, target_x, target_y
  
  
  def find_nearest_velocity(melvin_x, melvin_y, target_x, target_y, limitations):
    if (limitations['vxmin'] < 3 or limitations['vymin'] < 3):
      print(f"ERROR: Minimum speed limit exceeded!")
      return
    if (limitations['vxmax'] > 71 or limitations['vymax'] > 71):
      print(f"ERROR: Maximum speed limit exceeded!")
      return
    
    velx, vely, target_x, target_y = find_naive_velocity(melvin_x, melvin_y, target_x, target_y, limitations)
    while velx < limitations['vxmin']:
      if DEBUG_HERE:
        print('got to special case vx < vxmin')
      velx, vely, target_x, target_y = find_naive_velocity(melvin_x, melvin_y, target_x + 21600, target_y, limitations)
    
    while vely < limitations['vymin']:
      if DEBUG_HERE:
        print('got to special case vy < vymin')
      velx, vely, target_x, target_y = find_naive_velocity(melvin_x, melvin_y, target_x, target_y + 10800, limitations)
    
    if velx < limitations['vxmin'] or vely < limitations['vymin']:
      if DEBUG_HERE:
        print(f"Curr velx: {velx}, limit = {limitations['vxmin']}")
        print(f"Curr vely: {vely}, limit = {limitations['vymin']}")
        print("NO SOLUTIION WITH GIVEN LIMITS")
      return (False, -1)
    dist = math.sqrt((target_x - melvin_x) ** 2 + (target_y - melvin_y) ** 2)
    return (True, {'vx': round(velx, 2), 'vy': round(vely, 2), 'distance': dist})
  
  if not is_valid(vx_curr, vy_curr):
    print(f"Impossible to have given velocities vx = {vx_curr}, vy = {vy_curr}")
    return False

  if needs_slight_change(vx_curr, vy_curr):
    if vx_curr >= vy_curr:
      vx_curr = 4
    else:
      vy_curr = 4

  offset = 0
  while True:
    offset += 1
    l = {
      'vxmin' : max(3, int(vx_curr) - offset),
      'vymin' : max(3, int(vy_curr) - offset),
      'vxmax' : min(71, int(vx_curr) + offset),
      'vymax' : min(71, int(vy_curr) + offset),
      'vabs'  : min(71, math.sqrt(vx_curr ** 2 + vy_curr ** 2))
    }
    estimation = find_nearest_velocity(melvin_x, melvin_y, target_x, target_y, l)
    if estimation[0]:
      if is_valid(estimation[1]['vx'], estimation[1]['vy']): 
        return estimation[1]
    elif DEBUG_HERE: 
      print(f"Tried with (vxmin, vymin, vxmax, vymax) = {(l['vxmin'], l['vymin'], l['vxmax'], l['vymax'])}")
      print("didn't work. Repeating...")

def test_if_reaches(x1, y1, x2, y2, vx, vy, dis):
  vabs = math.sqrt(vx ** 2 + vy ** 2)
  time = dis / vabs
  x_arr = vx * time + x1
  y_arr = vy * time + y1
  x_calc = round(x_arr % 21600) 
  y_calc = round(y_arr % 10800)
  if x_calc == x2 and y_calc == y2:
    print("SUCCESS")
    return True
  else:
    print(f"FAIL\nx2 = {x2} but x_calculated = {x_calc}\ny2 = {y2} but y_calculated = {y_calc}")
    return False

if __name__ == "__main__":
  
  # GOOD CASES:
  
  # x = 10000
  # y = 5030
  # xdes = 10001
  # ydes = 8030
  # vxcurr = 11.42
  # vycurr = 70.08
  
  x = 15347
  y = 3
  xdes = 536
  ydes = 1
  vxcurr = 33.45
  vycurr = 63.11

  # import random
  # x = random.randint(0, 21600)
  # y = random.randint(0, 10800)
  # xdes = random.randint(0, 21600)
  # ydes = random.randint(0, 10800)
  # vxcurr = round(random.uniform(3, 71), 2)
  # vycurr = round(random.uniform(3, 71), 2)

  if SIMULATION:
    c = calculate_velocity(x, y, xdes, ydes, vxcurr, vycurr)
    if c:
      while True:
        c = calculate_velocity(x, y, xdes, ydes, vxcurr, vycurr)
        test_if_reaches(x, y, xdes, ydes, c['vx'], c['vy'], c['distance'])
        print(f"vx = {c['vx']:.2f}\nvy = {c['vy']:.2f}")
        print(f"distance = {c['distance']}\n")
        if c['vx'] != vxcurr or c['vy'] != vycurr:
          vxcurr, vycurr = c['vx'], c['vy']
        else:
          print("Reached required velocity.") 
          break
  else:
    c = calculate_velocity(x, y, xdes, ydes, vxcurr, vycurr)
    if c:
      test_if_reaches(x, y, xdes, ydes, c['vx'], c['vy'], c['distance'])
      print(f"vx = {c['vx']:.2f}\nvy = {c['vy']:.2f}")
      print(f"distance = {c['distance']}")
