import json
import urllib.parse
import os
import shutil

JSON_PATH = 'scenes.json'

def clear_screen():
    """Clears the console screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def load_scenes():
    """Loads scenes from scenes.json."""
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: {JSON_PATH} is corrupted. A new file will be created if you save.")
            return {"scenes": []}
    return {"scenes": []}

def save_scenes(config):
    """Saves the configuration to scenes.json after creating a backup."""
    if os.path.exists(JSON_PATH):
        backup_path = JSON_PATH + '.bak'
        shutil.copy2(JSON_PATH, backup_path)
        print(f"📝 Backup created at {backup_path}")

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    print("💾 scenes.json saved successfully!")

def list_scenes(config):
    """Prints a list of all current scenes."""
    clear_screen()
    print("--- Current Scenes ---")
    scenes = config.get('scenes', [])
    if not scenes:
        print("No scenes found.")
    else:
        for i, scene in enumerate(scenes):
            print(f"  [{i + 1}] {scene.get('name', 'Unnamed Scene')}")
    print("-" * 22)

def add_update_scene(config):
    """Adds a new scene or updates an existing one from a URL."""
    clear_screen()
    print("--- Add / Update Scene ---")
    print("Please paste Antilatency Environment URL:")
    url = input("URL: ").strip()

    if not url:
        print("Operation cancelled.")
        return

    try:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)

        if 'data' not in qs:
            print("\nError: 'data' parameter not found in URL.")
            return

        env_data = qs['data'][0]
        name = qs.get('name', ["Imported_Scene"])[0]

        found = False
        for scene in config['scenes']:
            if scene.get('name') == name:
                scene['environmentData'] = env_data
                print(f"\n✅ Updated existing scene: {name}")
                found = True
                break
        
        if not found:
            new_scene = {
                "name": name, 
                "environmentData": env_data, 
                "placementData": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            }
            config['scenes'].append(new_scene)
            print(f"\n✨ Added new scene: {name}")
        
        save_scenes(config)

    except Exception as e:
        print(f"\nError occurred while parsing URL: {e}")

def delete_scene(config):
    """Deletes a scene from the list."""
    while True:
        list_scenes(config)
        scenes = config.get('scenes', [])
        if not scenes:
            return

        print("Enter the number of the scene to delete (or 0 to cancel):")
        choice = input("> ").strip()

        if not choice.isdigit():
            print("Invalid input. Please enter a number.")
            input("Press Enter to continue...")
            continue

        choice_idx = int(choice)
        if choice_idx == 0:
            print("Operation cancelled.")
            return

        if 1 <= choice_idx <= len(scenes):
            scene_to_delete = scenes.pop(choice_idx - 1)
            scene_name = scene_to_delete.get('name', 'Unnamed Scene')
            print(f"\n🗑️ Scene '{scene_name}' has been deleted.")
            save_scenes(config)
            return
        else:
            print(f"Invalid number. Please enter a number between 1 and {len(scenes)}.")
            input("Press Enter to continue...")

def main_menu():
    """Displays the main menu and handles user interaction."""
    while True:
        config = load_scenes()
        clear_screen()
        print("=== Antilatency Scene Manager ===")
        print("  1. List all scenes")
        print("  2. Add / Update a scene (from URL)")
        print("  3. Delete a scene")
        print("  4. Exit")
        print("===============================")
        choice = input("Enter your choice: ").strip()

        if choice == '1':
            list_scenes(config)
            input("\nPress Enter to return to the menu...")
        elif choice == '2':
            add_update_scene(config)
            input("\nPress Enter to return to the menu...")
        elif choice == '3':
            delete_scene(config)
            input("\nPress Enter to return to the menu...")
        elif choice == '4':
            print("Exiting.")
            break
        else:
            print("Invalid choice, please try again.")
            input("Press Enter to continue...")

if __name__ == "__main__":
    main_menu()