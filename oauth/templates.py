"""HTML templates for OAuth and CLI login flows.

These templates are shared across main.py, setup.py, and railway.py
to eliminate duplication.
"""

# ============== OAuth Flow Templates ==============

LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Login - MCP Server</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
        .container {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                     width: 100%; max-width: 400px; }}
        h1 {{ margin: 0 0 10px; color: #333; font-size: 24px; }}
        p {{ color: #666; margin: 0 0 30px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; color: #333; font-weight: 500; }}
        input[type="email"], input[type="password"] {{
            width: 100%; padding: 12px; border: 2px solid #e1e1e1; border-radius: 8px;
            font-size: 16px; box-sizing: border-box; transition: border-color 0.2s; }}
        input:focus {{ outline: none; border-color: #667eea; }}
        button {{ width: 100%; padding: 14px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                 color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600;
                 cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; }}
        button:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }}
        .error {{ background: #fee; color: #c00; padding: 12px; border-radius: 8px; margin-bottom: 20px; }}
        .success {{ background: #e6ffed; color: #22863a; padding: 12px; border-radius: 8px; margin-bottom: 20px; }}
        .info {{ background: #f0f4ff; color: #4a5568; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }}
        .signup-link {{ text-align: center; margin-top: 20px; color: #666; }}
        .signup-link a {{ color: #667eea; text-decoration: none; font-weight: 500; }}
        .signup-link a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Sign In</h1>
        <p>Sign in to authorize MCP client access</p>
        {error}
        {success}
        <div class="info">MCP client is requesting access to server tools.</div>
        <form method="POST" action="/login">
            <input type="hidden" name="session" value="{session}">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required placeholder="your@email.com">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required placeholder="Your password">
            </div>
            <button type="submit">Sign In</button>
        </form>
        <div class="signup-link">
            Don't have an account? <a href="/signup?session={session}">Sign up</a>
        </div>
    </div>
</body>
</html>
"""

SIGNUP_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Sign Up - MCP Server</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
        .container {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                     width: 100%; max-width: 400px; }}
        h1 {{ margin: 0 0 10px; color: #333; font-size: 24px; }}
        p {{ color: #666; margin: 0 0 30px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; color: #333; font-weight: 500; }}
        input[type="email"], input[type="password"] {{
            width: 100%; padding: 12px; border: 2px solid #e1e1e1; border-radius: 8px;
            font-size: 16px; box-sizing: border-box; transition: border-color 0.2s; }}
        input:focus {{ outline: none; border-color: #667eea; }}
        button {{ width: 100%; padding: 14px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                 color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600;
                 cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; }}
        button:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }}
        .error {{ background: #fee; color: #c00; padding: 12px; border-radius: 8px; margin-bottom: 20px; }}
        .info {{ background: #f0f4ff; color: #4a5568; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }}
        .login-link {{ text-align: center; margin-top: 20px; color: #666; }}
        .login-link a {{ color: #667eea; text-decoration: none; font-weight: 500; }}
        .login-link a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Create Account</h1>
        <p>Sign up to use MCP server</p>
        {error}
        <div class="info">Create an account to authorize MCP client access.</div>
        <form method="POST" action="/signup">
            <input type="hidden" name="session" value="{session}">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required placeholder="your@email.com">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required placeholder="Create a password" minlength="6">
            </div>
            <div class="form-group">
                <label for="confirm_password">Confirm Password</label>
                <input type="password" id="confirm_password" name="confirm_password" required placeholder="Confirm your password" minlength="6">
            </div>
            <button type="submit">Create Account</button>
        </form>
        <div class="login-link">
            Already have an account? <a href="/login?session={session}">Sign in</a>
        </div>
    </div>
</body>
</html>
"""

CONSENT_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Authorize - MCP Server</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
        .container {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                     width: 100%; max-width: 450px; }}
        h1 {{ margin: 0 0 10px; color: #333; font-size: 24px; }}
        .app-info {{ display: flex; align-items: center; gap: 15px; padding: 20px; background: #f8f9fa;
                    border-radius: 8px; margin: 20px 0; }}
        .app-icon {{ width: 50px; height: 50px; background: #10a37f; border-radius: 10px;
                    display: flex; align-items: center; justify-content: center; color: white; font-size: 24px; }}
        .app-name {{ font-weight: 600; color: #333; }}
        .scopes {{ margin: 20px 0; }}
        .scope {{ display: flex; align-items: center; gap: 10px; padding: 12px; background: #f0f4ff;
                 border-radius: 8px; margin-bottom: 10px; }}
        .scope-icon {{ color: #667eea; }}
        .user-info {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
        .buttons {{ display: flex; gap: 12px; }}
        button {{ flex: 1; padding: 14px; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; }}
        .allow {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; }}
        .deny {{ background: white; color: #666; border: 2px solid #e1e1e1; }}
        .allow:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }}
        .deny:hover {{ background: #f5f5f5; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Authorize Access</h1>
        <div class="user-info">Logged in as: {user_email}</div>
        <div class="app-info">
            <div class="app-icon">M</div>
            <div>
                <div class="app-name">MCP Client</div>
                <div style="color: #666; font-size: 14px;">wants to access your account</div>
            </div>
        </div>
        <div class="scopes">
            <div class="scope">
                <span class="scope-icon">✓</span>
                <span>Access Echo and Ping tools</span>
            </div>
            <div class="scope">
                <span class="scope-icon">✓</span>
                <span>Read basic profile information</span>
            </div>
        </div>
        <form method="POST" action="/consent">
            <input type="hidden" name="session" value="{session}">
            <div class="buttons">
                <button type="submit" name="action" value="deny" class="deny">Deny</button>
                <button type="submit" name="action" value="allow" class="allow">Allow</button>
            </div>
        </form>
    </div>
</body>
</html>
"""


# ============== CLI Login Templates ==============

CLI_LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>CLI Login - Simple MCP Server</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
        .container {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                     width: 100%; max-width: 400px; }}
        h1 {{ margin: 0 0 10px; color: #333; font-size: 24px; }}
        p {{ color: #666; margin: 0 0 30px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; color: #333; font-weight: 500; }}
        input[type="email"], input[type="password"] {{
            width: 100%; padding: 12px; border: 2px solid #e1e1e1; border-radius: 8px;
            font-size: 16px; box-sizing: border-box; transition: border-color 0.2s; }}
        input:focus {{ outline: none; border-color: #667eea; }}
        button {{ width: 100%; padding: 14px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                 color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600;
                 cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; }}
        button:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }}
        .error {{ background: #fee; color: #c00; padding: 12px; border-radius: 8px; margin-bottom: 20px; }}
        .info {{ background: #f0f4ff; color: #4a5468; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }}
        .signup-link {{ text-align: center; margin-top: 20px; color: #666; }}
        .signup-link a {{ color: #667eea; text-decoration: none; font-weight: 500; }}
        .signup-link a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>CLI Login</h1>
        <p>Sign in to configure simple-mcp-server</p>
        {error}
        <div class="info">This will authenticate your local MCP server installation.</div>
        <form method="POST" action="/cli-login">
            <input type="hidden" name="session" value="{session}">
            <input type="hidden" name="port" value="{port}">
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required placeholder="your@email.com">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required placeholder="Your password">
            </div>
            <button type="submit">Sign In</button>
        </form>
        <div class="signup-link">
            Don't have an account? <a href="/cli-signup?session={session}&port={port}">Sign up</a>
        </div>
    </div>
</body>
</html>
"""

CLI_SIGNUP_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>CLI Sign Up - Simple MCP Server</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
               min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; }}
        .container {{ background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.2);
                     width: 100%; max-width: 400px; }}
        h1 {{ margin: 0 0 10px; color: #333; font-size: 24px; }}
        p {{ color: #666; margin: 0 0 30px; }}
        .form-group {{ margin-bottom: 20px; }}
        label {{ display: block; margin-bottom: 8px; color: #333; font-weight: 500; }}
        .optional {{ color: #999; font-weight: 400; font-size: 14px; }}
        input[type="email"], input[type="password"], input[type="text"] {{
            width: 100%; padding: 12px; border: 2px solid #e1e1e1; border-radius: 8px;
            font-size: 16px; box-sizing: border-box; transition: border-color 0.2s; }}
        input:focus {{ outline: none; border-color: #667eea; }}
        button {{ width: 100%; padding: 14px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                 color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600;
                 cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; }}
        button:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }}
        .error {{ background: #fee; color: #c00; padding: 12px; border-radius: 8px; margin-bottom: 20px; }}
        .info {{ background: #f0f4ff; color: #4a5468; padding: 12px; border-radius: 8px; margin-bottom: 20px; font-size: 14px; }}
        .login-link {{ text-align: center; margin-top: 20px; color: #666; }}
        .login-link a {{ color: #667eea; text-decoration: none; font-weight: 500; }}
        .login-link a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Create Account</h1>
        <p>Sign up to use simple-mcp-server</p>
        {error}
        <div class="info">Create an account to configure your MCP server.</div>
        <form method="POST" action="/cli-signup">
            <input type="hidden" name="session" value="{session}">
            <input type="hidden" name="port" value="{port}">
            <div class="form-group">
                <label for="name">Name</label>
                <input type="text" id="name" name="name" required placeholder="Your name">
            </div>
            <div class="form-group">
                <label for="organization">Organization <span class="optional">(optional)</span></label>
                <input type="text" id="organization" name="organization" placeholder="Your organization">
            </div>
            <div class="form-group">
                <label for="email">Email</label>
                <input type="email" id="email" name="email" required placeholder="your@email.com">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required placeholder="Create a password" minlength="6">
            </div>
            <div class="form-group">
                <label for="confirm_password">Confirm Password</label>
                <input type="password" id="confirm_password" name="confirm_password" required placeholder="Confirm your password" minlength="6">
            </div>
            <button type="submit">Create Account</button>
        </form>
        <div class="login-link">
            Already have an account? <a href="/cli-login?session={session}&port={port}">Sign in</a>
        </div>
    </div>
</body>
</html>
"""
