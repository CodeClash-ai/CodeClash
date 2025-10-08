import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { GamePicker } from './components/GamePicker';
import { GameViewer } from './components/GameViewer';
import './App.css';

function App() {
  return (
    <Router>
      <div className="app">
        <Routes>
          <Route path="/" element={<GamePicker />} />
          <Route path="/game/*" element={<GameViewer />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
