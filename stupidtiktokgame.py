import pygame
import sys
import random
import math
import pymunk
from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, GiftEvent, CommentEvent
import asyncio

# Initialize Pygame
pygame.init()

# Screen setup
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("TikTok Live Sword-Fighting Ball Arena")
FONT = pygame.font.Font(None, 36)

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
COLORS = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255), (0, 255, 255)]
COLOR_MAP = {"red": (255, 0, 0), "blue": (0, 0, 255), "green": (0, 255, 0), "yellow": (255, 255, 0), "purple": (255, 0, 255), "cyan": (0, 255, 255)}

# Arena and game settings
ARENA_WIDTH = WIDTH * 0.9
ARENA_HEIGHT = HEIGHT * 0.9
ARENA_LEFT = (WIDTH - ARENA_WIDTH) / 2
ARENA_TOP = (HEIGHT - ARENA_HEIGHT) / 2
ARENA_RIGHT = ARENA_LEFT + ARENA_WIDTH
ARENA_BOTTOM = ARENA_TOP + ARENA_HEIGHT
RESTITUTION = 0.8
BALL_RADIUS = 20
BALL_MASS = 1
SWORD_LENGTH = BALL_RADIUS * 1.5
SWORD_WIDTH = 5

# Spinning bar obstacle
BAR_LENGTH = 100
BAR_WIDTH = 10
BAR_SPEED = 0.05  # Radians per frame

# Pymunk space
space = pymunk.Space()
space.gravity = (0, 0)  # Default no gravity
global_gravity = 0

# Collision types
BALL_COLLISION_TYPE = 1
BAR_COLLISION_TYPE = 3

# Ball class
class Ball:
    def __init__(self, x, y, color, name):
        self.name = name
        self.color = color
        self.health = 100
        self.points = 0
        self.alive = True
        self.hit_flash = 0  # For hit effect
        self.trail = []  # List of (x, y, alpha) for trail
        self.sword_start = (0, 0)  # Initialize sword positions
        self.sword_end = (0, 0)

        # Pymunk body and shape for ball
        moment = pymunk.moment_for_circle(BALL_MASS, 0, BALL_RADIUS)
        self.body = pymunk.Body(mass=BALL_MASS, moment=moment)
        self.body.position = x, y
        self.body.velocity = random.uniform(-100, 100), random.uniform(-100, 100)
        self.shape = pymunk.Circle(self.body, BALL_RADIUS)
        self.shape.elasticity = RESTITUTION
        self.shape.collision_type = BALL_COLLISION_TYPE
        space.add(self.body, self.shape)

    def draw(self):
        if not self.alive:
            return
        x, y = self.body.position
        # Update trail (store last 10 positions)
        self.trail.append((x, y, 100))
        if len(self.trail) > 10:
            self.trail.pop(0)
        # Draw trail
        for i, (tx, ty, alpha) in enumerate(self.trail):
            alpha = alpha * (1 - i / len(self.trail))
            surface = pygame.Surface((BALL_RADIUS * 2, BALL_RADIUS * 2), pygame.SRCALPHA)
            pygame.draw.circle(surface, (*self.color, int(alpha)), (BALL_RADIUS, BALL_RADIUS), BALL_RADIUS)
            screen.blit(surface, (int(tx - BALL_RADIUS), int(ty - BALL_RADIUS)))

        # Draw ball with gradient
        surface = pygame.Surface((BALL_RADIUS * 2, BALL_RADIUS * 2), pygame.SRCALPHA)
        for r in range(BALL_RADIUS, 0, -1):
            alpha = int(255 * (r / BALL_RADIUS))
            color = self.color if self.hit_flash <= 0 else WHITE
            pygame.draw.circle(surface, (*color, alpha), (BALL_RADIUS, BALL_RADIUS), r)
        screen.blit(surface, (int(x - BALL_RADIUS), int(y - BALL_RADIUS)))

        # Draw sword and store positions
        angle = math.atan2(self.body.velocity[1], self.body.velocity[0])
        self.sword_start = (x, y)
        self.sword_end = (x + SWORD_LENGTH * math.cos(angle), y + SWORD_LENGTH * math.sin(angle))
        pygame.draw.line(screen, WHITE, self.sword_start, self.sword_end, SWORD_WIDTH)

        # Draw name and health
        text = FONT.render(f"{self.name}: {self.health}", True, WHITE)
        screen.blit(text, (int(x - BALL_RADIUS), int(y - BALL_RADIUS - 20)))

        # Update hit flash and particles
        if self.hit_flash > 0:
            self.hit_flash -= 1
            for _ in range(3):
                px = x + random.uniform(-BALL_RADIUS, BALL_RADIUS)
                py = y + random.uniform(-BALL_RADIUS, BALL_RADIUS)
                pygame.draw.circle(screen, self.color, (int(px), int(py)), 3)

    def update(self):
        if not self.alive:
            return
        # Apply global gravity
        self.body.velocity = (self.body.velocity[0], self.body.velocity[1] + global_gravity * 60)

# Spinning bar class
class SpinningBar:
    def __init__(self):
        self.angle = 0
        self.body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        self.body.position = (WIDTH / 2, HEIGHT / 2)
        self.shape = pymunk.Segment(self.body, (-BAR_LENGTH / 2, 0), (BAR_LENGTH / 2, 0), BAR_WIDTH / 2)
        self.shape.elasticity = RESTITUTION
        self.shape.collision_type = BAR_COLLISION_TYPE
        space.add(self.body, self.shape)

    def update(self):
        self.angle = (self.angle + BAR_SPEED) % (2 * math.pi)
        self.body.angle = self.angle

    def draw(self):
        x, y = self.body.position
        x1 = x + (BAR_LENGTH / 2) * math.cos(self.angle)
        y1 = y + (BAR_LENGTH / 2) * math.sin(self.angle)
        x2 = x - (BAR_LENGTH / 2) * math.cos(self.angle)
        y2 = y - (BAR_LENGTH / 2) * math.sin(self.angle)
        for i in range(int(BAR_WIDTH)):
            alpha = int(255 * (1 - i / BAR_WIDTH))
            pygame.draw.line(screen, (*WHITE, alpha), (x1, y1), (x2, y2), BAR_WIDTH - i)

# Game state
balls = []
leaderboard = {}  # {name: points}
spinning_bar = SpinningBar()

# Manual sword-to-ball collision detection
def check_sword_collisions():
    for i, ball in enumerate(balls):
        if not ball.alive:
            continue
        for j, other in enumerate(balls[i + 1:], i + 1):
            if not other.alive:
                continue
            # Check if ball's sword hits other ball
            if line_circle_collision(ball.sword_start, ball.sword_end, (other.body.position[0], other.body.position[1]), BALL_RADIUS):
                other.health -= 20
                other.hit_flash = 10
                if other.health <= 0 and other.alive:
                    other.alive = False
                    space.remove(other.shape, other.body)
                    leaderboard[ball.name] = leaderboard.get(ball.name, 0) + 10
            # Check if other ball's sword hits ball
            if line_circle_collision(other.sword_start, other.sword_end, (ball.body.position[0], ball.body.position[1]), BALL_RADIUS):
                ball.health -= 20
                ball.hit_flash = 10
                if ball.health <= 0 and ball.alive:
                    ball.alive = False
                    space.remove(ball.shape, ball.body)
                    leaderboard[other.name] = leaderboard.get(other.name, 0) + 10

# Line-circle collision detection
def line_circle_collision(line_start, line_end, circle_center, radius):
    line_vec = (line_end[0] - line_start[0], line_end[1] - line_start[1])
    circle_vec = (circle_center[0] - line_start[0], circle_center[1] - line_start[1])
    line_len = math.sqrt(line_vec[0]**2 + line_vec[1]**2)
    if line_len == 0:
        return False
    proj = (circle_vec[0] * line_vec[0] + circle_vec[1] * line_vec[1]) / line_len
    if proj < 0:
        closest = line_start
    elif proj > line_len:
        closest = line_end
    else:
        closest = (line_start[0] + proj * line_vec[0] / line_len, line_start[1] + proj * line_vec[1] / line_len)
    dist = math.sqrt((circle_center[0] - closest[0])**2 + (circle_center[1] - closest[1])**2)
    return dist <= radius

# Arena walls
def create_walls():
    static_body = space.static_body
    walls = [
        pymunk.Segment(static_body, (ARENA_LEFT, ARENA_TOP), (ARENA_RIGHT, ARENA_TOP), 1),
        pymunk.Segment(static_body, (ARENA_LEFT, ARENA_BOTTOM), (ARENA_RIGHT, ARENA_BOTTOM), 1),
        pymunk.Segment(static_body, (ARENA_LEFT, ARENA_TOP), (ARENA_LEFT, ARENA_BOTTOM), 1),
        pymunk.Segment(static_body, (ARENA_RIGHT, ARENA_TOP), (ARENA_RIGHT, ARENA_BOTTOM), 1)
    ]
    for wall in walls:
        wall.elasticity = RESTITUTION
        space.add(wall)

create_walls()

def create_ball(name, color=None):
    if len(balls) >= 50:
        return
    x = random.uniform(ARENA_LEFT + BALL_RADIUS, ARENA_RIGHT - BALL_RADIUS)
    y = random.uniform(ARENA_TOP + BALL_RADIUS, ARENA_BOTTOM - BALL_RADIUS)
    color = color or random.choice(COLORS)
    ball = Ball(x, y, color, name)
    balls.append(ball)
    leaderboard[name] = 0

# TikTok Live client setup
client = TikTokLiveClient(unique_id="your_actual_tiktok_username")  # Replace with your actual TikTok username

@client.on(ConnectEvent)
async def on_connect(event: ConnectEvent):
    print("Connected to TikTok Live!")

@client.on(GiftEvent)
async def on_gift(event: GiftEvent):
    if event.gift.streakable and not event.gift.streaking:
        return
    username = event.user.unique_id
    create_ball(username, random.choice(COLORS))
    print(f"{username} sent a gift and spawned a ball!")

@client.on(CommentEvent)
async def on_comment(event: CommentEvent):
    username = event.user.unique_id
    comment = event.comment.lower()
    if comment.startswith("!spawn"):
        create_ball(username, random.choice(COLORS))
        print(f"{username} spawned a ball with !spawn")
    elif comment.startswith("!boost"):
        for ball in balls:
            if ball.name == username and ball.alive:
                ball.body.velocity = (ball.body.velocity[0] * 1.5, ball.body.velocity[1] * 1.5)
                print(f"{username} boosted their ball!")
    elif comment.startswith("!color"):
        color_name = comment.split()[1] if len(comment.split()) > 1 else "red"
        for ball in balls:
            if ball.name == username and ball.alive:
                ball.color = COLOR_MAP.get(color_name, random.choice(COLORS))
                print(f"{username} changed their ball to {color_name}")
    elif comment.startswith("!gravity"):
        try:
            global global_gravity
            global_gravity = float(comment.split()[1]) if len(comment.split()) > 1 else 0
            global_gravity = max(-1, min(global_gravity, 1))
            print(f"{username} set gravity to {global_gravity}")
        except ValueError:
            print(f"{username} provided invalid gravity value")

def draw_leaderboard():
    sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)[:5]
    for i, (name, points) in enumerate(sorted_leaderboard):
        text = FONT.render(f"{i+1}. {name}: {points}", True, WHITE)
        screen.blit(text, (10, 10 + i * 30))

async def game_loop():
    create_ball("Player1")
    create_ball("Player2")

    try:
        await client.connect()
    except Exception as e:
        print(f"Failed to connect to TikTok Live: {e}. Running in offline mode.")

    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_s:
                    create_ball(f"Test{random.randint(1, 100)}")
                if event.key == pygame.K_b:
                    for ball in balls:
                        if ball.alive:
                            ball.body.velocity = (ball.body.velocity[0] * 1.5, ball.body.velocity[1] * 1.5)
                if event.key == pygame.K_c:
                    color_name = random.choice(list(COLOR_MAP.keys()))
                    for ball in balls:
                        if ball.alive:
                            ball.color = COLOR_MAP[color_name]
                if event.key == pygame.K_g:
                    global global_gravity
                    global_gravity = random.uniform(-0.5, 0.5)

        # Update physics
        space.step(1 / 60)

        # Check sword collisions
        check_sword_collisions()

        # Draw background (gradient from dark to light gray)
        for y in range(int(ARENA_TOP), int(ARENA_BOTTOM)):
            t = (y - ARENA_TOP) / ARENA_HEIGHT  # Normalized [0, 1]
            gray = int(50 + t * 100)  # Scale from 50 to 150
            pygame.draw.line(screen, (gray, gray, gray), (ARENA_LEFT, y), (ARENA_RIGHT, y))

        # Draw arena border
        pygame.draw.rect(screen, WHITE, (ARENA_LEFT, ARENA_TOP, ARENA_WIDTH, ARENA_HEIGHT), 2)

        # Update and draw game objects
        spinning_bar.update()
        spinning_bar.draw()
        for ball in balls:
            ball.update()
            ball.draw()

        # Draw leaderboard
        draw_leaderboard()
        pygame.display.flip()
        clock.tick(60)
        await asyncio.sleep(1.0 / 60)

def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(game_loop())
    finally:
        loop.close()

if __name__ == "__main__":
    main()
