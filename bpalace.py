from pyglet.gl import *
from pyglet.window import key
from pyglet import resource, sprite, font, image, graphics, media

import rooms

TILE_W, TILE_H = 32, 32
ROOM_TW, ROOM_TH = 16, 12
ROOMWIDTH = ROOM_TW * TILE_W
ROOMHEIGHT = ROOM_TH * TILE_H

# map codes from level editor.
C_TORCH = 1
C_ROPE = 2
C_ENDROPE = 4
C_SPRING = 5
C_CRAWLER = 8
C_BAT = 9
C_SPIDER = 12
C_SPIDERTOP = 10
C_BLOCKER = 16

# tile classes.
SOLID = (2,3,4,5,12,13,18,19,34,35)
CLIMBABLE = (8,10)
SUPPORTS = SOLID + CLIMBABLE
DAMAGE = (1,9,26)

# gameplay mechanics.
SPEED = 180
JUMP_FORCE = 4.9
GRAVITY = 10

# room display names.
NAMES = {
    (0,0): "The Great Hall",
}

def loadTiles(filename, tw, th):
    """Make a list of tiles from a tile sheet image"""
    img = pyglet.resource.image(filename)
    w,h = img.width, img.height
    numx,numy = w/tw, h/th
    return [img.get_region(x,h-y-th,tw,th)
                for y in xrange(0,numy*th,th)
                    for x in xrange(0,numx*tw,tw)]

def makeFlipped(tiles):
    """Append x-flipped versions of all tiles in a list"""
    flip = []
    for t in tiles:
        flip.append(t.get_transform(flip_x=True))
        flip[-1].anchor_x = 0 # undo translation
    return flip

def xcenterTiles(tiles):
    """Move the x-anchor to the center of each tile."""
    for t in tiles:
        t.anchor_x = t.width//2
    return tiles

def drawRope(tex, height, x, y):
    """Draw a rope by repeating a texture."""
    if height > 0:
        tv = height / float(tex.height)
        glEnable(tex.target)
        glBindTexture(tex.target, tex.id)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0)
        glVertex3f(x, y, 0)
        glTexCoord2f(0, -tv)
        glVertex3f(x, y - height, 0)
        glTexCoord2f(1, -tv)
        glVertex3f(x + tex.width, y - height, 0)
        glTexCoord2f(1, 0)
        glVertex3f(x + tex.width, y, 0)
        glEnd()
        glDisable(tex.target)

def plot(x,y):
    glBegin(GL_QUADS)
    glVertex3f(x, y, 0)
    glVertex3f(x, y+2, 0)
    glVertex3f(x+2, y+2, 0)
    glVertex3f(x+2, y, 0)
    glEnd()

def fillRect(x,y,w,h,r,g,b,a=1):
    glColor4f(r,g,b,a)
    glBegin(GL_QUADS)
    glVertex3f(x, y, 0)
    glVertex3f(x, y+h, 0)
    glVertex3f(x+w, y+h, 0)
    glVertex3f(x+w, y, 0)
    glEnd()
    glColor4f(1,1,1,1)


class TileSet(object):
    """A set of regular sized tile images."""

    def __init__(self, filename, tw, th, dw, dh):
        self.tiles = []
        self.tilewidth, self.tileheight = tw,th
        self.drawwidth, self.drawheight = dw, dh
        if filename:
            self.load(filename, tw, th)

    def load(self, filename, tw, th):
        """Load tiles from a packed tile sheet."""
        self.tilewidth, self.tileheight = tw,th
        img = pyglet.resource.image(filename)
        w,h = img.width, img.height
        numx,numy = w/tw, h/th
        self.tiles = [
            img.get_region(x,h-y-th,tw,th)
            for y in xrange(0,numy*th,th)
                for x in xrange(0,numx*tw,tw)]

    def draw(self, screen):
        """Draw all tiles for debugging."""
        x,y = 0,0
        for i in xrange(0,len(self.tiles)):
            screen.blit(self.tiles[i], (x,y))
            x=x+32
            if x>=32*8: x=0 ; y=y+32


class Room(object):
    """A tile-based game room."""

    x,y = 0,0
    mapwidth,mapheight = 1,1
    tilewidth,tileheight = 1,1
    bounce = 0 # displacement due to falling damage.

    def __init__(self, tileset, x, y, specials={}, codemap={}):
        self.tileset = tileset
        self.tilewidth, self.tileheight = tileset.drawwidth, tileset.drawheight
        self.x, self.y = x,y
        self.specials = specials
        self.codemap = codemap
        self.tiles = [] # private copy.
        self.codes = [] # shared, original room data.
        self.tilemap = [] # shared, original room data.
        self.colmap = [] # derived collision map.
        self.background = []
        self.sprites = []

    def draw(self):
        tiles = self.tiles
        numx,numy = len(tiles[0]), len(tiles)
        tw,th = self.tilewidth, self.tileheight
        posy = th * numy - th # start at the top.
        for y in xrange(0,numy):
            posx = 0
            row = tiles[y]
            for x in xrange(0,numx):
                t = row[x]
                if t:
                    t.blit(posx,posy,0)
                posx += tw
            posy -= th
        # draw sprite layers.
        for obj in self.background: obj.draw()
        for obj in self.sprites: obj.draw()

    def load(self, room, codes, objs):
        """Load a room and convert for rendering; spawn sprites."""
        self.background = []
        self.sprites = []
        w,h = len(room[0]), len(room)
        self.mapwidth, self.mapheight = w,h
        self.tiles = tiles = [[None for x in xrange(0,w)] for y in xrange(0,h)]
        self.colmap = colmap = [[0 for x in xrange(0,w)] for y in xrange(0,h)]
        self.tilemap = room # for tileTest.
        self.codes = codes # must set before calling factories.
        ts = self.tileset.tiles
        tw,th = self.tilewidth, self.tileheight
        top = th * h - th # origin of top tile.
        specials, codemap = self.specials, self.codemap
        for y in xrange(0,h):
            for x in xrange(0,w):
                num = room[y][x]
                tiles[y][x] = ts[num]
                if num in SOLID:
                    colmap[y][x] = 1
                code = codes[y][x]
                factory = codemap.get(code)
                if factory:
                    objs.append(factory(x*tw, top-y*th, self))

    def hitTest(self, x0, y0, x1, y1, check):
        """Hit-test a rectangle against solid map tiles."""
        tmap = self.tilemap
        ew,eh = len(tmap[0])-1,len(tmap)-1
        tx0 = max(0,x0//TILE_W)
        ty0 = max(0,y0//TILE_H)
        tx1 = min(ew,x1//TILE_W)
        ty1 = min(eh,y1//TILE_H)
        ty0,ty1 = eh-ty1,eh-ty0 # invert Y axis.
        for ty in xrange(ty0,ty1+1):
            row = tmap[ty]
            for tx in xrange(tx0,tx1+1):
                tile = row[tx]
                if tile in check:
                    return True, tx, eh-ty, tile
        return False, 0, 0, 0

    def tileTest(self, x, y, w, h, check):
        """Hit-test against the room tile layer."""
        tmap = self.tilemap
        ew,eh = len(tmap[0])-1,len(tmap)-1
        tx0 = max(0,x//TILE_W)
        ty0 = max(0,y//TILE_H)
        tx1 = min(ew,(x+w)//TILE_W)
        ty1 = min(eh,(y+h)//TILE_H)
        ty0,ty1 = eh-ty1,eh-ty0 # invert Y axis.
        for ty in xrange(ty0,ty1+1):
            row = tmap[ty]
            for tx in xrange(tx0,tx1+1):
                tile = row[tx]
                if tile in check:
                    return True, tx, eh-ty, tile
        return False, 0, 0, 0

    def scanForCode(self, x, y, dx, dy, code):
        """Scan the code layer in direction dx,dy for a value."""
        codes = self.codes
        cw,ch = len(codes[0]), len(codes)
        tw,th = self.tilewidth, self.tileheight
        top = th * ch - th # origin of top tile.
        cx,cy = x//tw, (top-y)//th # room coords to map cell.
        while cx>=0 and cy >=0 and cx<cw and cy<ch:
            if codes[cy][cx] == code:
                break
            cx += dx ; cy += dy
        return (cx*tw,top-cy*th) # map cell to room coords.


class Actor(sprite.Sprite):
    """Animated actor with tile collisions."""

    def __init__(self, frames, x, y, group=None):
        self.frames = frames
        sprite.Sprite.__init__(self, frames[0], x, y)

    def setFrame(self, index):
        if index < len(self.frames):
            frame = self.frames[index]
            if self.image is not frame: # avoid animation reset.
                self.image = frame

    def hitTest(self, x, y, w, h):
        """Conservative hit test for player collisions."""
        mx,my,mw,mh = self.x+4,self.y+4,self.width-8,self.height-8
        return x<mx+mw and x+w>mx and y<my+mh and y+h>my


class Player(Actor):

    velocity = 0
    anim = 0
    defecit = 0
    health = 100
    support = None # sprite we are standing on.

    def __init__(self, x, y, room):
        self.room = room
        tiles = loadTiles("belle.png", 32, 48)
        flipped = makeFlipped(tiles)
        right = [tiles[n] for n in (1,2,3,2)]
        left = [flipped[n] for n in (1,2,3,2)]
        climb = [tiles[5], flipped[5]]
        frames = [
            image.Animation.from_image_sequence(right, 12/60.0, True),
            image.Animation.from_image_sequence(left, 12/60.0, True),
            image.Animation.from_image_sequence(climb, 8/60.0, True),
            tiles[0], flipped[0], climb[0], # stationary
            tiles[4], flipped[4], climb[0], # jumping
        ]
        Actor.__init__(self, frames, x, y)
        self.jump_snd = pyglet.resource.media("jump.wav", streaming=False)

    def move(self, dx, dy, jump, dt):
        """Process player input."""
        w,h = 32,32
        ox,rw,rh = 2,w-4-1,h-1 # smaller collision rect.

        oldx,oldy = int(self.x),int(self.y)
        moved = False

        # issues:
        # - when falling onto a climbable tile, the player falls inside
        #   the tile by whatever velocity they have at impact.
        # - bouncing at tops of ladders.
        # - climbable means both up and down at once.

        # test for climbable tiles or sprites in contact with the player.
        # note we do not look below the player's feet here, we do that later.
        qx,qy = oldx + ox, oldy
        canClimb,hx,hy,tn = self.room.tileTest(qx, qy-1, rw, rh+1, CLIMBABLE)
        if not canClimb:
            # test only background sprites; ropes.
            for obj in self.room.background:
                if getattr(obj, "climbable", 0):
                    if obj.hitTest(qx, qy, rw, rh):
                        canClimb = True
                        break

        # accumulate move adjustments until we move at least one pixel,
        # then hittest the area covered by the integer movement.
        adjx = self.x + SPEED*dx
        newx = int(adjx)
        if newx > oldx: # moving right.
            hit,hx,hy,tc = self.room.hitTest(oldx+ox+rw, oldy, newx+ox+rw, oldy+rh, SOLID)
            self.x = hx*TILE_W-(rw+1)-ox if hit else adjx
            self.anim = 0
            moved = True
        elif newx < oldx: # moving left.
            hit,hx,hy,tc = self.room.hitTest(newx+ox, oldy, oldx+ox, oldy+rh, SOLID)
            self.x = (hx+1)*TILE_W-ox if hit else adjx
            self.anim = 1
            moved = True
        else:
            self.x = adjx # accumulate movement.

        # determine vertical movement.
        support = self.support
        climbed = False
        adjy = self.y
        if canClimb:
            # allow the player to climb.
            if dy != 0:
                adjy = self.y + SPEED*dy
                self.anim = 2
                moved = True
                climbed = True
                self.stopFalling() # stop jumping or falling.
            else:
                # allow jumping but not falling.
                self.velocity += dt * -GRAVITY
                if self.velocity > 0:
                    adjy = self.y + self.velocity
                else:
                    self.stopFalling()
        else:
            # apply gravity.
            self.velocity += dt * -GRAVITY
            adjy = self.y + self.velocity

        # apply vertical movement unless on a support sprite.
        supported = canClimb
        newy = int(adjy)
        newx = int(self.x) + ox
        if newy > oldy: # moving up.
            support = None # climbed off support.
            hit,hx,hy,tc = self.room.hitTest(newx, oldy+rh, newx+rw, newy+rh, SOLID)
            if hit:
                self.y = hy*TILE_H-(rh+1)
                if self.velocity > 0:
                    self.velocity = 0 # stop upward velocity.
            else:
                self.y = adjy
        elif newy < oldy: # moving down.
            support = None # moved off support.
            hit,hx,hy,tc = self.room.hitTest(newx, newy, newx+rw, oldy, SOLID)
            if hit:
                self.y = (hy+1)*TILE_H
                supported = True
                self.stopFalling()
            else:
                # would fall: check for a supporting sprite below us.
                qh = oldy - newy
                for obj in self.room.background:
                    if getattr(obj, "supports", 0):
                        if obj.hitTest(newx, newy, rw, qh):
                            if support is None or obj.y + obj.level > support.y + support.level:
                                support = obj
                if support is None:
                    # no support: free fall.
                    self.y = adjy
        else:
            self.y = adjy # accumulate movement.

        if support is not None:
            supported = True

        # check for jump input if standing on something.
        # avoid jumping while climbing since it spam-jumps every frame!
        # velocity <=0 avoids spam-jumping when jumping up ladders.
        # TODO: still spam-jumps when something is above your head.
        if jump and supported and not climbed and self.velocity <= 0:
            self.velocity = JUMP_FORCE
            if support is not None:
                func = getattr(support, "actorJump", None)
                if func: func(self)
            self.jump_snd.play()
            support = None # jumped off support.

        # notify supports if our support has changed.
        if support is not self.support:
            #print "CHANGED SUPPORT"
            # notify our old support, if any.
            func = getattr(self.support, "lostActor", None)
            if func: func(self)
            # notify our new support.
            self.support = support
            func = getattr(support, "gainActor", None)
            if func: func(self)

        # this must deal with actor position and velocity.
        if support is not None:
            support.supportActor(self)

        if self.velocity != 0:
            # show a jump/fall frame.
            self.setFrame(self.anim + 6)
        elif moved and supported:
            # show animated walk or climb.
            self.setFrame(self.anim)
        else:
            # show an idle frame.
            self.setFrame(self.anim + 3)

    def stopFalling(self):
        if self.velocity < -8:
            # take falling damage.
            damage = (-self.velocity-8)*3
            #print "DAMAGE", damage, self.velocity
            self.defecit += damage
            self.room.bounce = min(int(damage/2),4) # limit to 4.
        self.velocity = 0

    def update(self, dt):
        pass

    def checkDamage(self):
        # conservative collision rect for the player.
        qx,qy,rw,rh = int(self.x) + 6, int(self.y), 32-12, 28
        damage,hx,hy,tn = self.room.tileTest(qx, qy, rw, rh, DAMAGE)
        if not damage:
            # hit-test all enemy sprites.
            for obj in self.room.sprites:
                if getattr(obj, "hurtful", 0):
                    if obj.hitTest(qx, qy, rw, rh):
                        damage = True
                        break
        if damage:
            self.defecit += 1


class Torch(sprite.Sprite):
    """Animated torch fixture."""
    def __init__(self, x, y, room):
        tiles = loadTiles("flame.png", 32, 32)
        frames = image.Animation.from_image_sequence(tiles, 0.2, True)
        sprite.Sprite.__init__(self, frames, x, y)
        room.background.append(self)
    def update(self, dt):
        pass


class DropRope(object):
    """Rope that moves up and down."""

    height = 0
    rate = SPEED*2/3
    LEFT = 14 # position inside the tile.
    climbable = True

    def __init__(self, x, y, room):
        ex,ey = room.scanForCode(x,y,0,1,C_ENDROPE)
        y += TILE_H # start from top edge of tile.
        self.limit = y - ey
        self.texture = pyglet.resource.texture("rope.png")
        self.x, self.y = self.LEFT + x, y
        self.width = self.texture.width
        room.background.append(self)

    def update(self, dt):
        self.height += self.rate * dt
        if self.height > self.limit:
            self.height = self.limit
            self.rate = -self.rate
        elif self.height < 0:
            self.height = 0
            self.rate = -self.rate

    def draw(self):
        drawRope(self.texture, self.height, self.x, self.y)

    def hitTest(self, x, y, w, h):
        """Exact hit test with fix for reversed y coordinate"""
        mx,my,mw,mh = self.x,self.y-self.height,self.width,self.height
        return x<mx+mw and x+w>mx and y<my+mh and y+h>my


class SpringBoard(sprite.Sprite):
    """A bouncy platform on a spring."""

    supports = True
    maxLevel = 24
    level = maxLevel # support height level.
    kinetic = 0

    def __init__(self, x, y, room):
        self.frames = loadTiles("spring.png", 32, 32)
        sprite.Sprite.__init__(self, self.frames[0], x, y)
        room.background.append(self)

    def update(self, dt):
        """Drain away kinetic energy."""
        if self.kinetic > 0:
            self.kinetic -= 5*dt
            if self.kinetic < 0: self.kinetic = 0
        steps = min(int(self.kinetic), 3) # limit 3
        self.image = self.frames[steps]
        self.level = self.maxLevel - steps * 4
        #print "KSL", self.kinetic, steps, self.level

    def supportActor(self, other):
        """Reposition the actor and clear velocity."""
        other.y = self.y + self.level
        other.velocity = 0

    def actorJump(self, other):
        """Boost the jump using our kinetic energy."""
        other.velocity += self.kinetic
        self.kinetic = 0
        self.update(0)

    def gainActor(self, other):
        """Notify that an actor has landed on us."""
        if other.velocity < 0:
            force = int(-other.velocity-2)
            self.kinetic += force
            self.update(0)
            other.velocity = 0 # soak up velocity.

    def hitTest(self, x, y, w, h):
        """Hit-test against the current spring level."""
        mx,my,mw,mh = self.x+8,self.y,self.width-12,self.level
        return x<mx+mw and x+w>mx and y<my+mh and y+h>my


class HorzEnemy(Actor):
    """Enemy that moves horizontally between blocker codes."""

    FILENAME = ""
    FRAME_W,FRAME_H = 32,32
    ANIM = False
    rate = -SPEED*2/3 # initially moving left.

    def __init__(self, x, y, room):
        sx,sy = room.scanForCode(x, y, -1, 0, C_BLOCKER)
        ex,ey = room.scanForCode(x, y, 1, 0, C_BLOCKER)
        # adjust to avoid entering the blocker tiles.
        self.left, self.right = sx + TILE_W, ex - TILE_W
        tiles = loadTiles(self.FILENAME, self.FRAME_W, self.FRAME_H)
        flipped = makeFlipped(tiles)
        if self.ANIM:
            tiles = [
                image.Animation.from_image_sequence(tiles, 0.25, True),
                image.Animation.from_image_sequence(flipped, 0.25, True),
            ]
        else:
            tiles.extend(flipped)
        Actor.__init__(self, tiles, x, y)
        room.sprites.append(self)

    def update(self, dt):
        self.x += self.rate * dt
        if self.x > self.right:
            self.x = self.right
            self.rate = -self.rate
            self.setFrame(0)
        elif self.x < self.left:
            self.x = self.left
            self.rate = -self.rate
            self.setFrame(1)


class Crawler(HorzEnemy):
    """Crawls along the ground."""
    FILENAME = "crawler.png"
    hurtful = True


class Bat(HorzEnemy):
    """Flies left and right."""
    FILENAME = "bat.png"
    ANIM = True
    hurtful = True


class Spider(Actor):
    """Moves up and down on a sliver of web."""
    rate = SPEED/3 # initially moving down.
    LEFT = 14 # position of web inside the tile.
    hurtful = True

    def __init__(self, x, y, room):
        sx,sy = room.scanForCode(x, y, 0, -1, C_SPIDERTOP)
        self.top, self.bottom = sy, y
        y = sy # start at the top.
        self.texture = pyglet.resource.texture("sliver.png")
        tiles = loadTiles("spider.png", 32, 32)
        anim = image.Animation.from_image_sequence(tiles, 12/60.0, True)
        Actor.__init__(self, [anim], x, y)
        room.sprites.append(self)

    def update(self, dt):
        self.y += self.rate * dt
        if self.y > self.top:
            self.y = self.top
            self.rate = -self.rate
        elif self.y < self.bottom:
            self.y = self.bottom
            self.rate = -self.rate

    def draw(self):
        Actor.draw(self)
        x,y = self.x + self.LEFT, self.top + TILE_H
        drawRope(self.texture, self.top - self.y, x, y)


codemap = {
    C_TORCH:    Torch,
    C_ROPE:     DropRope,
    C_SPRING:   SpringBoard,
    C_CRAWLER:  Crawler,
    C_BAT:      Bat,
    C_SPIDER:   Spider,
}


class Game(object):
    """The game controller."""

    def __init__(self, window):
        """Set up the game state."""
        self.window = window
        window.push_handlers(self)
        self.keys = key.KeyStateHandler()
        window.push_handlers(self.keys)
        self.roomX, self.roomY = 8,8
        pyglet.resource.add_font("8bitlimo.ttf")
        self.font = font.load('8-bit Limit O BRK', 16, bold=False, italic=False)
        self.hfont = font.load('8-bit Limit O BRK', 36, bold=False, italic=False)
        self.ts = TileSet("tiles.png", 32, 32, 32, 32)
        self.room = Room(self.ts, 0, 32, codemap=codemap)
        self.fps_display = pyglet.clock.ClockDisplay()
        self.ouch = pyglet.resource.media("ouch.wav", streaming=False)
        self.hbar = sprite.Sprite(pyglet.resource.image("health.png"),
                                  x=10, y=self.window.height-25)
        self.loadTitle()
        pyglet.clock.schedule(self.update)
        pyglet.clock.schedule_interval(self.checkHealth, 0.125)

    def loadTitle(self):
        self.player = Player(10*32, 1*32, self.room)
        self.player.setFrame(4)
        self.loadRoom(0,0)
        self.inRoom = True
        self.playing = False
        self.menuIndex = 0

    def on_draw(self):
        self.window.clear()
        glLoadIdentity()
        glTranslatef(14,0,0)
        if self.inRoom:
            glPushMatrix()
            glTranslatef(self.room.x, self.room.y - self.room.bounce, 0)
            self.room.draw()
            self.player.draw()
            glPopMatrix()
        # player health bar.
        if self.playing:
            x,y=10,self.window.height-10
            if self.player.health > 0:
                fillRect(x+3,y-12,1+self.player.health*2,9,0.25,1,0.25)
            self.hbar.draw()
            # room name.
            self.title.draw()
            self.roomnum.draw()
        else:
            font.Text(self.hfont, "Belle of", x=90, y=320).draw()
            font.Text(self.hfont, "Nine Fables", x=120, y=270).draw()
            x,y = 200,200
            for item in ("Continue","New Game","Instructions","Exit"):
                font.Text(self.font, item, x=x, y=y).draw()
                y -= 24
            font.Text(self.font, ">", x=x-20, y=200+2-self.menuIndex*24).draw()
        #self.fps_display.draw()

    def on_key_press(self, symbol, modifiers):
        if symbol == key.F12:
            pyglet.image.get_buffer_manager().get_color_buffer().save('screenshot.png')
        if not self.playing:
            if symbol == key.W or symbol == key.UP or symbol == key.APOSTROPHE:
                self.menuIndex = (self.menuIndex - 1) & 3
            if symbol == key.S or symbol == key.DOWN or symbol == key.SLASH:
                self.menuIndex = (self.menuIndex + 1) & 3
            if symbol == key.SPACE or symbol == key.ENTER:
                self.startGame()

    def update(self, dt):
        if self.inRoom and self.playing:
            # apply player movement.
            keys = self.keys
            dx,dy = 0,0
            if keys[key.A] or keys[key.LEFT] or keys[key.Z]:
                dx = -dt
            if keys[key.D] or keys[key.RIGHT] or keys[key.X]:
                dx = dt
            if keys[key.W] or keys[key.UP] or keys[key.APOSTROPHE]:
                dy = dt
            if keys[key.S] or keys[key.DOWN] or keys[key.SLASH]:
                dy = -dt
            jump = keys[key.SPACE] or keys[key.ENTER]
            self.player.move(dx, dy, jump, dt)

            # change room when the player reaches the edge.
            x,y = self.player.x, self.player.y
            if x < 0:
                self.player.x = ROOMWIDTH-TILE_W
                self.changeRoom(-1,0)
            elif x > ROOMWIDTH-TILE_W:
                self.player.x = 0
                self.changeRoom(1,0)
            if y < 0:
                self.player.y = ROOMHEIGHT-TILE_H
                self.changeRoom(0,1)
            elif y > ROOMHEIGHT-TILE_H:
                self.player.y = 0
                self.changeRoom(0,-1)

            # update all objects
            for s in self.objs:
                s.update(dt)

    def checkHealth(self, dt):
        if self.room.bounce > 0:
            self.room.bounce -= 1
        if self.player.health > 0:
            self.player.checkDamage()
            if self.player.defecit > 0:
                self.player.defecit -= 1
                self.player.health -= 1
                self.ouch.play()

    def startGame(self):
        self.changeRoom(0,0)
        self.player.x, self.player.y = 8*32, 1*32
        self.playing = True

    def changeRoom(self,x,y):
        """Clear active room, schedule next room."""
        self.roomX = max(self.roomX + x, 0)
        self.roomY = max(self.roomY + y, 0)
        self.inRoom = False
        self.loadRoom(self.roomX, self.roomY)
        def nextRoom(dt):
            self.inRoom = True
        pyglet.clock.schedule_once(nextRoom, 0.25)

    def loadRoom(self, roomX, roomY):
        roomId = roomY * rooms.width + roomX
        tiles = rooms.rooms[roomId*2]
        codes = rooms.rooms[roomId*2+1]
        self.objs = [self.player]
        self.room.load(tiles, codes, self.objs)
        base = self.window.height - 52
        ix,iy = roomX-8,roomY-8 # relative to start.
        self.title = font.Text(self.font,
            NAMES.get((ix,iy),"Belle of Nine Fables"), x=10, y=base)
        self.roomnum = font.Text(self.font,
            "%d:%d" % (abs(ix),abs(iy)), x=280, y=base)


def main():
    resource.path.insert(0, 'data')
    resource.reindex()
    window = pyglet.window.Window(width=540, height=480, caption="Belle of Nine Fables")
    game = Game(window)
    pyglet.app.run()
