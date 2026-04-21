import pygame
import sys


pygame.init()


WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Wand Warrior")

# Colors
BLACK      = (0,   0,   0  )
WHITE      = (255, 255, 255)
GOLD       = (255, 215, 0  )
DARK_BLUE  = (10,  10,  40 )
LIGHT_BLUE = (100, 149, 237)

# Fonts
title_font  = pygame.font.SysFont("Arial", 72, bold=True)
prompt_font = pygame.font.SysFont("Arial", 32)
hint_font   = pygame.font.SysFont("Arial", 20)

def draw_intro_screen(blink_visible):
    screen.fill(DARK_BLUE)


    title_text = title_font.render("WAND WARRIOR", True, GOLD)
    title_rect = title_text.get_rect(center=(WIDTH // 2, HEIGHT // 3))
    screen.blit(title_text, title_rect)


    sub_text = hint_font.render("Slash the objects before they disappear!", True, LIGHT_BLUE)
    sub_rect  = sub_text.get_rect(center=(WIDTH // 2, HEIGHT // 3 + 70))
    screen.blit(sub_text, sub_rect)

    if blink_visible:
        prompt_text = prompt_font.render("Press SPACE to Play", True, WHITE)
        prompt_rect = prompt_text.get_rect(center=(WIDTH // 2, HEIGHT * 2 // 3))
        screen.blit(prompt_text, prompt_rect)


    quit_text = hint_font.render("Press ESC to Quit", True, (150, 150, 150))
    quit_rect = quit_text.get_rect(center=(WIDTH // 2, HEIGHT - 40))
    screen.blit(quit_text, quit_rect)

    pygame.display.flip()

def main():
    clock        = pygame.time.Clock()
    blink_timer  = 0
    blink_visible = True

    while True:
        dt = clock.tick(60)  
        blink_timer += dt

        
        if blink_timer >= 500:
            blink_visible = not blink_visible
            blink_timer   = 0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.key == pygame.K_SPACE:
                    print("Starting game...") #would replace with soemthing later
                    return  

        draw_intro_screen(blink_visible)

if __name__ == "__main__":
    main()

FPS = 60
LANES = ['LEFT', 'UP', 'DOWN', 'RIGHT']
LANE_X_POSITIONS = [150, 300, 450, 600] # x positions for each arrow

# notes represented as a list of dictionaries, each containing the time (ms)) and the lane for the note, and hit accuracy 

beatmap1 = [
    {'time': 1000, 'lane': 'LEFT', 'hit': False}, #hits are initialized to false 
    {'time': 1700, 'lane': 'UP', 'hit': False},
    {'time': 2200, 'lane': 'RIGHT', 'hit': False},
    {'time': 2600, 'lane': 'DOWN', 'hit': False},
]

scroll_speed = 0.5 # pixels per ms, adjust for faster or slower note movement
hit_line_y = 550 # y position of the hit line = 550


# 2: setup pygame stuff and create a window

pygame.init()  # initializes pygame modules
screen = pygame.display.set_mode((WIDTH, HEIGHT))  # creates game window
pygame.display.set_caption("Rythmn Game")  # game window title
clock = pygame.time.Clock() # for frame rate
font = pygame.font.SysFont("Hattori_Han_Sans", 36) # for displaying score and stuff

# 3: assets (arrows, audio, score, etc)

score = 0
combo = 0

hit_messages = []

pygame.mixer.init() # initialize mixer for audio
pygame.mixer.music.load('audiomap1.mp3') # load music
pygame.mixer.music.play() # play music

# 4: gesture and accuracy functions
message = "Miss"

def process_gesture(lane, time_of_hit):
    global score, combo, hit_messages
    # find the closest note in the lane that hasn't been hit yet
    closest_note = None
    min_time_diff = float('inf')

    for note in beatmap1:
        if note['lane'] == lane and not note['hit']:
            time_diff = abs(note['time'] - time_of_hit)
            if time_diff < min_time_diff:
                min_time_diff = time_diff
                closest_note = note

    # determine hit accuracy based on time difference
    if closest_note and min_time_diff <= 200: # 200 ms window for a hit
        closest_note['hit'] = True
        if min_time_diff <= 80:
            score += 100 # perfect hit
            combo += 1
            message = "Perfect"
        elif min_time_diff <= 120:
            score += 50 # good hit
            combo += 1
            message = "Good"
        else:
            score += 40 # bad hit
            combo = 0 # reset combo on bad hit
            message = "Bad"
    else:
        combo = 0 # reset combo on miss
        message = "Miss"

    # determine message
    if closest_note and min_time_diff <= 200:
        if min_time_diff <= 80:
            message = "Perfect"
        elif min_time_diff <= 120:
            message = "Good"
        else:
            message = "Bad"
    else:
        message = "Miss"

    # get position for message
    lane_index = LANES.index(lane)
    x = LANE_X_POSITIONS[lane_index]
    y = hit_line_y - 60

    hit_messages.append({'text': message, 'timer': 500, 'x': x, 'y': y})

# store message

def draw_notes(note, song_time):
    y = hit_line_y - (note['time'] - song_time) * scroll_speed
    if 0 <= y <= HEIGHT: # only draw if within screen bounds
        lane_index = LANES.index(note['lane'])
        x = LANE_X_POSITIONS[lane_index]
        pygame.draw.circle(screen, (250, 0, 0), (x, y), 35) # draw a circle for the note

# reset button function        
def draw_restart_button():
    button_rect = pygame.Rect(650, 20, 120, 50)

    pygame.draw.rect(screen, (200, 200, 200), button_rect)
    pygame.draw.rect(screen, (0, 0, 0), button_rect, 2)

    font = pygame.font.SysFont(None, 30)
    text = font.render("Restart", True, (0, 0, 0))

    screen.blit(text, (button_rect.x + 20, button_rect.y + 15))

    return button_rect

def restart_game():
    global score, combo

    score = 0
    combo = 0

    for note in beatmap1:
        note['hit'] = False

    pygame.mixer.music.stop()
    pygame.mixer.music.play()


def draw_score():
    score_text = font.render(f"Score: {score}", True, (255, 255, 255))  # white color
    screen.blit(score_text, (10, 10))  # top-left corner


# 5: main game loop
running = True
start_ticks = pygame.time.get_ticks() # start time for timing notes

while running:
    clock.tick(FPS) 
    song_time = pygame.mixer.music.get_pos() # get current song time in ms

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        # check for key presses and determine if they hit a note
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                process_gesture('LEFT', song_time) # placeholder for gesture processing
            elif event.key == pygame.K_UP:
                process_gesture('UP', song_time) 
            elif event.key == pygame.K_DOWN:
                process_gesture('DOWN', song_time) 
            elif event.key == pygame.K_RIGHT:
                process_gesture('RIGHT', song_time)
            else:
                continue # ignore other keys

          # if restart button clicked
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()

            if button_rect.collidepoint(mouse_pos):
                restart_game()
        
 # 6 : draw everything
    screen.fill((0, 0, 0)) # clear screen with black

    button_rect = draw_restart_button()

    for note in beatmap1:
        draw_notes(note, song_time) # draw each note based on current song time
    
    # draw score 
    draw_score()

    for msg in hit_messages[:]:
        if msg['text'] == "Perfect":
          color = (0, 255, 0)
        elif msg['text'] == "Good":
           color = (255, 255, 0)
        else:
            color = (255, 0, 0)

        text_surface = font.render(msg['text'], True, color)
        screen.blit(text_surface, (msg['x'] - text_surface.get_width() // 2, msg['y']))

        msg['timer'] -= clock.get_time()
        if msg['timer'] <= 0:
            hit_messages.remove(msg)
    
    pygame.draw.line(screen, (250, 250, 250), (100, hit_line_y), (700, hit_line_y), 9)

    pygame.display.flip()


pygame.quit() # clean up pygame
sys.exit()
