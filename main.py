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