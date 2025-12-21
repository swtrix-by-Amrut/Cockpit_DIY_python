#!/usr/bin/env python3
"""
Simple User Management Script for Server Cockpit (Plain Text Passwords)
Usage: python3 manage_users_simple.py
"""

import csv
import os
import sys

USERS_FILE = 'config/users.csv'

def load_users():
    """Load all users from CSV"""
    if not os.path.exists(USERS_FILE):
        return []
    
    users = []
    with open(USERS_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            users.append(row)
    return users

def save_users(users):
    """Save users to CSV"""
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, 'w', newline='') as f:
        fieldnames = ['username', 'password', 'is_admin']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(users)

def list_users():
    """List all users"""
    users = load_users()
    if not users:
        print("No users found.")
        return
    
    print("\n" + "=" * 80)
    print("Current Users:")
    print("=" * 80)
    print(f"{'#':<4} {'Username':<20} {'Password':<20} {'Role':<10}")
    print("-" * 80)
    for i, user in enumerate(users, 1):
        admin_status = "Admin" if user['is_admin'].lower() == 'true' else "User"
        print(f"{i:<4} {user['username']:<20} {user['password']:<20} {admin_status:<10}")
    print("=" * 80)

def add_user():
    """Add a new user"""
    users = load_users()
    
    print("\n" + "=" * 60)
    print("Add New User")
    print("=" * 60)
    
    # Get username
    username = input("Username: ")
    
    # username = input("Username: ").strip()
    # if not username:
        # print("❌ Username cannot be empty")
        # return
    
    # Check if username exists
    if any(u['username'] == username for u in users):
        print(f"❌ Username '{username}' already exists")
        return
    
    # Get password
    password = input("Password: ").strip()
    if not password:
        print("❌ Password cannot be empty")
        return
    
    # Get admin status
    is_admin = input("Admin user? (y/n): ").strip().lower()
    is_admin = 'true' if is_admin == 'y' else 'false'
    
    # Add user
    users.append({
        'username': username,
        'password': password,
        'is_admin': is_admin
    })
    
    save_users(users)
    print(f"\n✓ User '{username}' added successfully!")

def delete_user():
    """Delete a user"""
    users = load_users()
    
    if not users:
        print("No users to delete.")
        return
    
    list_users()
    
    print("\n" + "=" * 60)
    print("Delete User")
    print("=" * 60)
    
    username = input("Username to delete: ").strip()
    
    # Find user
    user_index = None
    for i, user in enumerate(users):
        if user['username'] == username:
            user_index = i
            break
    
    if user_index is None:
        print(f"❌ User '{username}' not found")
        return
    
    # Confirm deletion
    confirm = input(f"Are you sure you want to delete '{username}'? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Deletion cancelled")
        return
    
    # Delete user
    users.pop(user_index)
    save_users(users)
    print(f"✓ User '{username}' deleted successfully!")

def change_password():
    """Change user password"""
    users = load_users()
    
    if not users:
        print("No users found.")
        return
    
    list_users()
    
    print("\n" + "=" * 60)
    print("Change Password")
    print("=" * 60)
    
    username = input("Username: ").strip()
    
    # Find user
    user_index = None
    for i, user in enumerate(users):
        if user['username'] == username:
            user_index = i
            break
    
    if user_index is None:
        print(f"❌ User '{username}' not found")
        return
    
    # Get new password
    password = input("New password: ").strip()
    if not password:
        print("❌ Password cannot be empty")
        return
    
    # Update password
    users[user_index]['password'] = password
    save_users(users)
    print(f"✓ Password for '{username}' changed successfully!")

def change_admin_status():
    """Change user admin status"""
    users = load_users()
    
    if not users:
        print("No users found.")
        return
    
    list_users()
    
    print("\n" + "=" * 60)
    print("Change Admin Status")
    print("=" * 60)
    
    username = input("Username: ").strip()
    
    # Find user
    user_index = None
    for i, user in enumerate(users):
        if user['username'] == username:
            user_index = i
            break
    
    if user_index is None:
        print(f"❌ User '{username}' not found")
        return
    
    current_status = users[user_index]['is_admin'].lower() == 'true'
    new_status = not current_status
    
    print(f"Current status: {'Admin' if current_status else 'User'}")
    print(f"New status: {'Admin' if new_status else 'User'}")
    
    confirm = input("Confirm change? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Change cancelled")
        return
    
    users[user_index]['is_admin'] = 'true' if new_status else 'false'
    save_users(users)
    print(f"✓ Admin status for '{username}' changed successfully!")

def show_menu():
    """Display main menu"""
    print("\n" + "=" * 60)
    print("Server Cockpit - User Management (Plain Text)")
    print("=" * 60)
    print("1. List users")
    print("2. Add user")
    print("3. Delete user")
    print("4. Change password")
    print("5. Change admin status")
    print("0. Exit")
    print("=" * 60)

def main():
    """Main program loop"""
    while True:
        show_menu()
        
        try:
            choice = input("\nSelect option: ").strip()
            
            if choice == '1':
                list_users()
            elif choice == '2':
                add_user()
            elif choice == '3':
                delete_user()
            elif choice == '4':
                change_password()
            elif choice == '5':
                change_admin_status()
            elif choice == '0':
                print("\nGoodbye!")
                break
            else:
                print("❌ Invalid option")
        
        except KeyboardInterrupt:
            print("\n\n❌ Cancelled by user")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == '__main__':
    main()