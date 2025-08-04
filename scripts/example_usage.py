#!/usr/bin/env python3
"""
AI 驅動的智能 Prompt 生成器使用示例
展示如何使用工具驅動的系統生成提示詞
"""

import sys
from pathlib import Path

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.ai_prompt_generator import AIPromptGenerator


def example_web_app_analysis():
    """Web 應用分析示例"""
    print("🌐 Web 應用分析示例")
    print("=" * 50)

    # 模擬一個 React 項目路徑
    project_path = "/tmp/example-react-app"

    # 創建示例項目結構
    create_example_react_project(project_path)

    # 創建 AI 生成器
    generator = AIPromptGenerator(project_path)

    # 使用工具生成提示詞
    prompt_content = generator.generate_prompt_with_tools()

    # 保存提示詞
    output_file = generator.save_prompt_with_tools(prompt_content, "web-app-prompt.md")

    print(f"✅ Web 應用提示詞已生成: {output_file}")
    return output_file


def example_api_service_analysis():
    """API 服務分析示例"""
    print("\n🔌 API 服務分析示例")
    print("=" * 50)

    # 模擬一個 Express 項目路徑
    project_path = "/tmp/example-express-api"

    # 創建示例項目結構
    create_example_express_project(project_path)

    # 創建 AI 生成器
    generator = AIPromptGenerator(project_path)

    # 使用工具生成提示詞
    prompt_content = generator.generate_prompt_with_tools()

    # 保存提示詞
    output_file = generator.save_prompt_with_tools(
        prompt_content, "api-service-prompt.md"
    )

    print(f"✅ API 服務提示詞已生成: {output_file}")
    return output_file


def example_mobile_app_analysis():
    """移動應用分析示例"""
    print("\n📱 移動應用分析示例")
    print("=" * 50)

    # 模擬一個 React Native 項目路徑
    project_path = "/tmp/example-react-native-app"

    # 創建示例項目結構
    create_example_react_native_project(project_path)

    # 創建 AI 生成器
    generator = AIPromptGenerator(project_path)

    # 使用工具生成提示詞
    prompt_content = generator.generate_prompt_with_tools()

    # 保存提示詞
    output_file = generator.save_prompt_with_tools(
        prompt_content, "mobile-app-prompt.md"
    )

    print(f"✅ 移動應用提示詞已生成: {output_file}")
    return output_file


def create_example_react_project(project_path: str):
    """創建示例 React 項目"""
    project_dir = Path(project_path)
    project_dir.mkdir(parents=True, exist_ok=True)

    # 創建 package.json
    package_json = {
        "name": "example-react-app",
        "version": "1.0.0",
        "description": "A modern React application",
        "main": "index.js",
        "scripts": {
            "start": "react-scripts start",
            "build": "react-scripts build",
            "test": "react-scripts test",
            "eject": "react-scripts eject",
        },
        "dependencies": {
            "react": "^18.2.0",
            "react-dom": "^18.2.0",
            "react-router-dom": "^6.8.0",
            "@reduxjs/toolkit": "^1.9.0",
            "react-redux": "^8.0.0",
            "axios": "^1.3.0",
        },
        "devDependencies": {
            "react-scripts": "5.0.1",
            "@testing-library/react": "^13.4.0",
            "@testing-library/jest-dom": "^5.16.5",
            "eslint": "^8.35.0",
            "prettier": "^2.8.0",
        },
    }

    with open(project_dir / "package.json", "w") as f:
        import json

        json.dump(package_json, f, indent=2)

    # 創建 README.md
    readme_content = """# Example React App

## Features
- Modern React 18 with Hooks
- Redux Toolkit for state management
- React Router for navigation
- Axios for API calls
- TypeScript support
- ESLint and Prettier for code quality

## Technical Requirements
- React 18.2.0 or higher
- Node.js 16.0.0 or higher
- npm or yarn package manager
- Modern browser support (Chrome, Firefox, Safari, Edge)

## Getting Started
1. Install dependencies: `npm install`
2. Start development server: `npm start`
3. Build for production: `npm run build`
4. Run tests: `npm test`

## Project Structure
```
src/
├── components/     # Reusable components
├── pages/         # Page components
├── store/         # Redux store configuration
├── hooks/         # Custom React hooks
├── utils/         # Utility functions
└── styles/        # CSS and styling
```

## Performance Requirements
- Page load time < 3 seconds
- Interactive response time < 100ms
- Support 100+ concurrent users
- Lighthouse score > 90

## Security Requirements
- Input validation on all forms
- XSS protection
- CSRF protection
- Secure API communication
"""

    with open(project_dir / "README.md", "w") as f:
        f.write(readme_content)

    # 創建 src 目錄和示例文件
    src_dir = project_dir / "src"
    src_dir.mkdir(exist_ok=True)

    # 創建 App.js
    app_js = """import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Provider } from 'react-redux';
import { store } from './store';
import Home from './pages/Home';
import About from './pages/About';
import './styles/App.css';

function App() {
  return (
    <Provider store={store}>
      <Router>
        <div className="App">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/about" element={<About />} />
          </Routes>
        </div>
      </Router>
    </Provider>
  );
}

export default App;
"""

    with open(src_dir / "App.js", "w") as f:
        f.write(app_js)

    # 創建 store 配置
    store_dir = src_dir / "store"
    store_dir.mkdir(exist_ok=True)

    store_js = """import { configureStore } from '@reduxjs/toolkit';
import userReducer from './userSlice';

export const store = configureStore({
  reducer: {
    user: userReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
"""

    with open(store_dir / "index.js", "w") as f:
        f.write(store_js)

    print(f"✅ 示例 React 項目已創建: {project_path}")


def create_example_express_project(project_path: str):
    """創建示例 Express 項目"""
    project_dir = Path(project_path)
    project_dir.mkdir(parents=True, exist_ok=True)

    # 創建 package.json
    package_json = {
        "name": "example-express-api",
        "version": "1.0.0",
        "description": "A RESTful API built with Express.js",
        "main": "server.js",
        "scripts": {
            "start": "node server.js",
            "dev": "nodemon server.js",
            "test": "jest",
            "lint": "eslint .",
        },
        "dependencies": {
            "express": "^4.18.2",
            "cors": "^2.8.5",
            "helmet": "^6.0.1",
            "morgan": "^1.10.0",
            "dotenv": "^16.0.3",
            "jsonwebtoken": "^9.0.0",
            "bcryptjs": "^2.4.3",
            "mongoose": "^7.0.0",
            "joi": "^17.9.0",
        },
        "devDependencies": {
            "nodemon": "^2.0.20",
            "jest": "^29.4.0",
            "supertest": "^6.3.0",
            "eslint": "^8.35.0",
        },
    }

    with open(project_dir / "package.json", "w") as f:
        import json

        json.dump(package_json, f, indent=2)

    # 創建 README.md
    readme_content = """# Example Express API

## Features
- RESTful API design
- JWT authentication
- Input validation with Joi
- MongoDB integration
- CORS support
- Security headers with Helmet
- Request logging with Morgan

## Technical Requirements
- Node.js 16.0.0 or higher
- MongoDB 5.0 or higher
- Express.js 4.18.0 or higher
- JWT for authentication
- bcryptjs for password hashing

## API Endpoints
- `GET /api/users` - Get all users
- `POST /api/users` - Create new user
- `GET /api/users/:id` - Get user by ID
- `PUT /api/users/:id` - Update user
- `DELETE /api/users/:id` - Delete user
- `POST /api/auth/login` - User login
- `POST /api/auth/register` - User registration

## Performance Requirements
- Response time < 200ms
- Support 1000+ QPS
- 99.9% uptime
- Horizontal scaling support

## Security Requirements
- Input validation on all endpoints
- SQL injection protection
- JWT token authentication
- Password encryption with bcrypt
- CORS configuration
- Security headers
"""

    with open(project_dir / "README.md", "w") as f:
        f.write(readme_content)

    # 創建 server.js
    server_js = """const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(helmet());
app.use(cors());
app.use(morgan('combined'));
app.use(express.json());

// Routes
app.use('/api/users', require('./routes/users'));
app.use('/api/auth', require('./routes/auth'));

// Error handling middleware
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({ error: 'Something went wrong!' });
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
"""

    with open(project_dir / "server.js", "w") as f:
        f.write(server_js)

    # 創建 routes 目錄
    routes_dir = project_dir / "routes"
    routes_dir.mkdir(exist_ok=True)

    users_js = """const express = require('express');
const router = express.Router();
const { validateUser } = require('../middleware/validation');
const { authenticateToken } = require('../middleware/auth');

// Get all users
router.get('/', authenticateToken, async (req, res) => {
  try {
    // Implementation here
    res.json({ users: [] });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Create new user
router.post('/', validateUser, async (req, res) => {
  try {
    // Implementation here
    res.status(201).json({ message: 'User created successfully' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
"""

    with open(routes_dir / "users.js", "w") as f:
        f.write(users_js)

    print(f"✅ 示例 Express 項目已創建: {project_path}")


def create_example_react_native_project(project_path: str):
    """創建示例 React Native 項目"""
    project_dir = Path(project_path)
    project_dir.mkdir(parents=True, exist_ok=True)

    # 創建 package.json
    package_json = {
        "name": "example-react-native-app",
        "version": "1.0.0",
        "description": "A React Native mobile application",
        "main": "index.js",
        "scripts": {
            "android": "react-native run-android",
            "ios": "react-native run-ios",
            "start": "react-native start",
            "test": "jest",
            "lint": "eslint .",
        },
        "dependencies": {
            "react": "18.2.0",
            "react-native": "0.71.0",
            "@react-navigation/native": "^6.1.0",
            "@react-navigation/stack": "^6.3.0",
            "@reduxjs/toolkit": "^1.9.0",
            "react-redux": "^8.0.0",
            "@react-native-async-storage/async-storage": "^1.18.0",
            "react-native-vector-icons": "^9.2.0",
        },
        "devDependencies": {
            "@babel/core": "^7.20.0",
            "@babel/preset-env": "^7.20.0",
            "@babel/runtime": "^7.20.0",
            "@react-native/eslint-config": "^0.71.0",
            "@react-native/metro-config": "^0.71.0",
            "@tsconfig/react-native": "^2.0.0",
            "@types/react": "^18.0.0",
            "@types/react-test-renderer": "^18.0.0",
            "babel-jest": "^29.2.1",
            "eslint": "^8.19.0",
            "jest": "^29.2.1",
            "metro-react-native-babel-preset": "0.76.0",
            "prettier": "^2.4.1",
            "react-test-renderer": "18.2.0",
            "typescript": "4.8.4",
        },
    }

    with open(project_dir / "package.json", "w") as f:
        import json

        json.dump(package_json, f, indent=2)

    # 創建 README.md
    readme_content = """# Example React Native App

## Features
- Cross-platform mobile development
- React Navigation for navigation
- Redux Toolkit for state management
- AsyncStorage for local storage
- Vector icons support
- TypeScript support

## Technical Requirements
- React Native 0.71.0 or higher
- Node.js 16.0.0 or higher
- React Navigation 6.0.0 or higher
- Redux Toolkit for state management
- AsyncStorage for data persistence

## Platform Support
- iOS 12.0 or higher
- Android API level 21 or higher
- React Native CLI
- Metro bundler

## Performance Requirements
- App launch time < 3 seconds
- Memory usage < 100MB
- Battery optimization
- Offline functionality support

## Security Requirements
- Secure data storage
- Network communication security
- User privacy protection
- Code obfuscation
"""

    with open(project_dir / "README.md", "w") as f:
        f.write(readme_content)

    # 創建 App.js
    app_js = """import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { Provider } from 'react-redux';
import { store } from './src/store';
import HomeScreen from './src/screens/HomeScreen';
import DetailScreen from './src/screens/DetailScreen';

const Stack = createStackNavigator();

const App = () => {
  return (
    <Provider store={store}>
      <NavigationContainer>
        <Stack.Navigator>
          <Stack.Screen name="Home" component={HomeScreen} />
          <Stack.Screen name="Detail" component={DetailScreen} />
        </Stack.Navigator>
      </NavigationContainer>
    </Provider>
  );
};

export default App;
"""

    with open(project_dir / "App.js", "w") as f:
        f.write(app_js)

    # 創建 src 目錄結構
    src_dir = project_dir / "src"
    src_dir.mkdir(exist_ok=True)

    screens_dir = src_dir / "screens"
    screens_dir.mkdir(exist_ok=True)

    # 創建 HomeScreen.js
    home_screen_js = """import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { useSelector, useDispatch } from 'react-redux';

const HomeScreen = ({ navigation }) => {
  const user = useSelector(state => state.user);
  const dispatch = useDispatch();

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Welcome to React Native App</Text>
      <TouchableOpacity
        style={styles.button}
        onPress={() => navigation.navigate('Detail')}
      >
        <Text style={styles.buttonText}>Go to Detail</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F5FCFF',
  },
  title: {
    fontSize: 20,
    textAlign: 'center',
    margin: 10,
  },
  button: {
    backgroundColor: '#007AFF',
    padding: 10,
    borderRadius: 5,
    marginTop: 20,
  },
  buttonText: {
    color: 'white',
    textAlign: 'center',
  },
});

export default HomeScreen;
"""

    with open(screens_dir / "HomeScreen.js", "w") as f:
        f.write(home_screen_js)

    print(f"✅ 示例 React Native 項目已創建: {project_path}")


def main():
    """主函數 - 運行所有示例"""
    print("🚀 AI 驅動的智能 Prompt 生成器示例")
    print("=" * 60)

    try:
        # 運行 Web 應用示例
        web_app_file = example_web_app_analysis()

        # 運行 API 服務示例
        api_service_file = example_api_service_analysis()

        # 運行移動應用示例
        mobile_app_file = example_mobile_app_analysis()

        print("\n" + "=" * 60)
        print("🎉 所有示例運行完成!")
        print("📄 生成的文件:")
        print(f"   - Web 應用提示詞: {web_app_file}")
        print(f"   - API 服務提示詞: {api_service_file}")
        print(f"   - 移動應用提示詞: {mobile_app_file}")
        print("\n💡 提示:這些示例展示了如何使用工具驅動的系統生成不同類型的提示詞")

    except Exception as e:
        print(f"❌ 運行示例時出錯: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
