#!/usr/bin/env python3
import getpass
from pylast import md5
try:
   input = raw_input
except NameError:
   pass

if __name__ == '__main__':
    print("This saves your username and a hash of your password to file login.secret.")
    username = input("Enter your username: ")
    password = getpass.getpass("Enter your password: ")
    hash = md5(password)
    password = None
    print("Your password hash: " + hash)
    print("Saving to to login.secret")
    with open('login.secret', 'w') as login:
        login.write(username + "\n" + hash + "\n")

# End of file
