import csv
import os

class AuthManager:
    def __init__(self, users_file='config/users.csv'):
        self.users_file = users_file
        self._ensure_file_exists()
    
    def _ensure_file_exists(self):
        if not os.path.exists(self.users_file):
            os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
            # Create default users file with headers
            with open(self.users_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['username', 'password', 'is_admin'])
                # Default: admin/admin123, user/user123
                writer.writerow(['admin', 'admin123', 'true'])
                writer.writerow(['user', 'user123', 'false'])
    
    def authenticate(self, username, password):
        with open(self.users_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['username'] == username and row['password'] == password:
                    return {
                        'username': username,
                        'is_admin': row['is_admin'].lower() == 'true'
                    }
        return None
    
    def change_password(self, username, old_password, new_password):
        if not self.authenticate(username, old_password):
            return {'success': False, 'error': 'Invalid current password'}
        
        users = []
        with open(self.users_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['username'] == username:
                    row['password'] = new_password
                users.append(row)
        
        with open(self.users_file, 'w', newline='') as f:
            fieldnames = ['username', 'password', 'is_admin']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(users)
        
        return {'success': True}


# Standalone test
if __name__ == '__main__':
    print("Testing AuthManager...")
    auth = AuthManager('test_users.csv')
    
    # Test authentication
    result = auth.authenticate('admin', 'admin123')
    print(f"Admin login: {result}")
    
    result = auth.authenticate('user', 'user123')
    print(f"User login: {result}")
    
    result = auth.authenticate('admin', 'wrong')
    print(f"Wrong password: {result}")
    
    # Clean up
    if os.path.exists('test_users.csv'):
        os.remove('test_users.csv') 