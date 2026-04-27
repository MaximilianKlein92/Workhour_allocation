import random
from pathlib import Path


def get_images_from_folder(folder_name):
    image_dir = Path(__file__).parent / folder_name
    if not image_dir.exists():
        return []

    image_files = []
    for extension in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.gif"):
        image_files.extend(image_dir.glob(extension))

    return sorted(image_files)


def get_random_image_from_folder(folder_name):
    image_files = get_images_from_folder(folder_name)
    if not image_files:
        return None

    return random.choice(image_files)


def get_random_media_image():
    return get_random_image_from_folder("Media")
