#!/usr/bin/env python3
"""
Photo Resizer for JasonCookingBook
Resizes all JPG photos to be between 500KB-800KB while maintaining quality
"""

import os
import sys
import shutil
from PIL import Image, ImageOps
import argparse
from pathlib import Path

def get_file_size_kb(filepath):
    """Get file size in KB"""
    return os.path.getsize(filepath) / 1024

def create_backup(image_path, backup_dir):
    """Create backup of original file"""
    backup_path = Path(backup_dir)
    backup_path.mkdir(parents=True, exist_ok=True)
    
    # Maintain directory structure in backup
    rel_path = Path(image_path).relative_to(Path('source'))
    backup_file = backup_path / rel_path
    backup_file.parent.mkdir(parents=True, exist_ok=True)
    
    shutil.copy2(image_path, backup_file)
    return backup_file

def resize_image_to_target_size(image_path, target_min_kb=500, target_max_kb=800, quality_start=85, backup_dir=None):
    """
    Resize image to target file size range
    """
    print(f"Processing: {image_path}")
    
    # Get original size
    original_size_kb = get_file_size_kb(image_path)
    print(f"  Original size: {original_size_kb:.1f} KB")
    
    # If already in target range, skip
    if target_min_kb <= original_size_kb <= target_max_kb:
        print(f"  ✓ Already in target range, skipping")
        return True
    
    # Create backup if requested
    if backup_dir:
        try:
            backup_file = create_backup(image_path, backup_dir)
            print(f"  📁 Backup created: {backup_file}")
        except Exception as e:
            print(f"  ⚠ Failed to create backup: {e}")
            return False
    
    try:
        # Open and auto-rotate image based on EXIF
        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)
            
            # Convert to RGB if necessary (handles RGBA, etc.)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            original_width, original_height = img.size
            print(f"  Original dimensions: {original_width}x{original_height}")
            
            # If file is smaller than target, we might need to reduce quality only
            if original_size_kb < target_min_kb:
                print(f"  File is smaller than target minimum, keeping original")
                return True
            
            # Start with original dimensions and adjust
            width, height = original_width, original_height
            quality = quality_start
            
            # If image is very large, start by reducing dimensions
            if original_size_kb > target_max_kb * 3:  # Much larger than target
                # Calculate scale factor to get roughly in range
                scale_factor = (target_max_kb * 1024 / (original_size_kb * 1024)) ** 0.5
                width = int(original_width * scale_factor)
                height = int(original_height * scale_factor)
                print(f"  Scaling to: {width}x{height}")
            
            # Binary search for optimal size
            attempts = 0
            max_attempts = 15
            
            while attempts < max_attempts:
                # Resize image
                if width != original_width or height != original_height:
                    resized_img = img.resize((width, height), Image.Resampling.LANCZOS)
                else:
                    resized_img = img
                
                # Save to temporary location to check size
                temp_path = image_path + ".temp"
                resized_img.save(temp_path, 'JPEG', quality=quality, optimize=True)
                
                temp_size_kb = get_file_size_kb(temp_path)
                print(f"  Attempt {attempts + 1}: {width}x{height}, quality={quality}, size={temp_size_kb:.1f}KB")
                
                # Check if we're in target range
                if target_min_kb <= temp_size_kb <= target_max_kb:
                    # Success! Replace original
                    os.replace(temp_path, image_path)
                    print(f"  ✓ Resized to {temp_size_kb:.1f} KB")
                    return True
                
                # Adjust parameters
                if temp_size_kb > target_max_kb:
                    # Too large - reduce quality or dimensions
                    if quality > 60:
                        quality -= 5
                    else:
                        # Reduce dimensions
                        width = int(width * 0.9)
                        height = int(height * 0.9)
                        quality = min(85, quality + 10)  # Reset quality when reducing size
                else:
                    # Too small - increase quality or dimensions (but prefer staying small)
                    if quality < 95:
                        quality += 5
                    else:
                        break  # Accept smaller size rather than going over
                
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                
                attempts += 1
            
            # If we couldn't get exact range, use the last attempt if it's reasonable
            if os.path.exists(temp_path):
                final_size = get_file_size_kb(temp_path)
                if final_size <= target_max_kb * 1.2:  # Allow 20% over target
                    os.replace(temp_path, image_path)
                    print(f"  ✓ Final size: {final_size:.1f} KB (close enough)")
                    return True
                else:
                    os.remove(temp_path)
            
            print(f"  ⚠ Could not achieve target size after {max_attempts} attempts")
            return False
            
    except Exception as e:
        print(f"  ✗ Error processing {image_path}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Resize photos in JasonCookingBook to target size range')
    parser.add_argument('--min-size', type=int, default=500, help='Minimum target size in KB (default: 500)')
    parser.add_argument('--max-size', type=int, default=800, help='Maximum target size in KB (default: 800)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--source-dir', default='source', help='Source directory to process (default: source)')
    parser.add_argument('--backup', action='store_true', help='Create backup of original files before resizing')
    parser.add_argument('--backup-dir', default='backup_originals', help='Directory to store backups (default: backup_originals)')
    
    args = parser.parse_args()
    
    # Find all JPG files
    source_path = Path(args.source_dir)
    if not source_path.exists():
        print(f"Error: Source directory '{args.source_dir}' not found")
        sys.exit(1)
    
    jpg_files = list(source_path.rglob('*.jpg')) + list(source_path.rglob('*.JPG'))
    
    if not jpg_files:
        print("No JPG files found in source directory")
        return
    
    print(f"Found {len(jpg_files)} JPG files")
    print(f"Target size range: {args.min_size}-{args.max_size} KB")
    
    if args.dry_run:
        print("\n=== DRY RUN MODE ===")
        for jpg_file in jpg_files:
            size_kb = get_file_size_kb(jpg_file)
            status = "✓ OK" if args.min_size <= size_kb <= args.max_size else "⚠ NEEDS RESIZE"
            print(f"{jpg_file}: {size_kb:.1f} KB - {status}")
        return
    
    # Process files
    print(f"\nProcessing {len(jpg_files)} files...")
    success_count = 0
    
    # Create backup directory if needed
    backup_dir = args.backup_dir if args.backup else None
    
    for i, jpg_file in enumerate(jpg_files, 1):
        print(f"\n[{i}/{len(jpg_files)}]", end=" ")
        if resize_image_to_target_size(str(jpg_file), args.min_size, args.max_size, backup_dir=backup_dir):
            success_count += 1
    
    print(f"\n=== SUMMARY ===")
    print(f"Successfully processed: {success_count}/{len(jpg_files)} files")
    
    if success_count < len(jpg_files):
        print(f"Failed to process: {len(jpg_files) - success_count} files")

if __name__ == "__main__":
    main()
