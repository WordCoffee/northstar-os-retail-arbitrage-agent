import { useRef, useEffect, useState } from 'react';

export default function DrawingCanvas({ onPredict, isPredicting, classNames }) {
  const canvasRef = useRef(null);
  const [drawing, setDrawing] = useState(false);
  const [lastPoint, setLastPoint] = useState(null);
  const [predictions, setPredictions] = useState([]);
  const [currentWord, setCurrentWord] = useState('');
  const [showResult, setShowResult] = useState(false);

  const canvasSize = 280;
  const lineWidth = 12;

  const getCanvasCoords = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const clientY = e.touches ? e.touches[0].clientY : e.clientY;
    return {
      x: clientX - rect.left,
      y: clientY - rect.top
    };
  };

  const startDrawing = (e) => {
    e.preventDefault();
    const coords = getCanvasCoords(e);
    setDrawing(true);
    setLastPoint(coords);
    setShowResult(false);
    setPredictions([]);
  };

  const draw = (e) => {
    if (!drawing) return;
    e.preventDefault();
    const coords = getCanvasCoords(e);
    const ctx = canvasRef.current.getContext('2d');
    
    ctx.beginPath();
    ctx.moveTo(lastPoint.x, lastPoint.y);
    ctx.lineTo(coords.x, coords.y);
    ctx.strokeStyle = '#000';
    ctx.lineWidth = lineWidth;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();
    
    setLastPoint(coords);
  };

  const stopDrawing = () => {
    setDrawing(false);
    setLastPoint(null);
    if (onPredict && canvasRef.current) {
      predictDrawing();
    }
  };

  const predictDrawing = async () => {
    if (!canvasRef.current || !onPredict) return;
    setShowResult(true);
    const preds = await onPredict(canvasRef.current);
    setPredictions(preds);
  };

  const clearCanvas = () => {
    const ctx = canvasRef.current.getContext('2d');
    ctx.clearRect(0, 0, canvasSize, canvasSize);
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvasSize, canvasSize);
    setPredictions([]);
    setShowResult(false);
  };

  useEffect(() => {
    const ctx = canvasRef.current.getContext('2d');
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvasSize, canvasSize);
    ctx.lineWidth = lineWidth;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    canvas.addEventListener('mousedown', startDrawing);
    canvas.addEventListener('mousemove', draw);
    canvas.addEventListener('mouseup', stopDrawing);
    canvas.addEventListener('mouseleave', stopDrawing);
    canvas.addEventListener('touchstart', startDrawing, { passive: false });
    canvas.addEventListener('touchmove', draw, { passive: false });
    canvas.addEventListener('touchend', stopDrawing);
    return () => {
      canvas.removeEventListener('mousedown', startDrawing);
      canvas.removeEventListener('mousemove', draw);
      canvas.removeEventListener('mouseup', stopDrawing);
      canvas.removeEventListener('mouseleave', stopDrawing);
      canvas.removeEventListener('touchstart', startDrawing);
      canvas.removeEventListener('touchmove', draw);
      canvas.removeEventListener('touchend', stopDrawing);
    };
  }, [drawing, lastPoint]);

  const getRandomWord = () => {
    const words = classNames || [
      'apple', 'banana', 'cat', 'dog', 'tree', 'house', 'car', 'flower',
      'sun', 'moon', 'star', 'heart', 'book', 'cup', 'phone', 'chair'
    ];
    return words[Math.floor(Math.random() * words.length)];
  };

  const handleNewGame = () => {
    clearCanvas();
    setCurrentWord(getRandomWord());
  };

  useEffect(() => {
    if (!currentWord) {
      setCurrentWord(getRandomWord());
    }
  }, [currentWord, classNames]);

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>Quick, Draw!</h1>
        <div style={styles.wordContainer}>
          <span style={styles.wordLabel}>Draw:</span>
          <span style={styles.word}>{currentWord}</span>
        </div>
      </div>

      <div style={styles.canvasWrapper}>
        <canvas
          ref={canvasRef}
          width={canvasSize}
          height={canvasSize}
          style={styles.canvas}
        />
      </div>

      {showResult && predictions.length > 0 && (
        <div style={styles.results}>
          <h3 style={styles.resultsTitle}>AI Guesses:</h3>
          <div style={styles.predictions}>
            {predictions.slice(0, 5).map((pred, i) => (
              <div key={i} style={styles.prediction}>
                <span style={styles.rank}>#{i + 1}</span>
                <span style={styles.label}>{pred.className}</span>
                <span style={styles.confidence}>
                  {(pred.probability * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
          {predictions[0]?.className.toLowerCase() === currentWord.toLowerCase() && (
            <div style={styles.correct}>🎉 Correct! The AI guessed it!</div>
          )}
        </div>
      )}

      <div style={styles.controls}>
        <button 
          onClick={clearCanvas} 
          disabled={isPredicting}
          style={{ ...styles.button, ...styles.clearButton }}
        >
          {isPredicting ? 'Thinking...' : 'Clear'}
        </button>
        <button 
          onClick={handleNewGame}
          style={styles.button}
        >
          New Word
        </button>
      </div>

      <div style={styles.hint}>
        Draw the word above in 20 seconds. The AI will guess what you drew!
      </div>
    </div>
  );
}

const styles = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    padding: '20px',
    fontFamily: 'system-ui, sans-serif',
    maxWidth: '400px',
    margin: '0 auto',
    minHeight: '100vh',
    background: '#f5f5f5'
  },
  header: {
    textAlign: 'center',
    marginBottom: '20px',
    width: '100%'
  },
  title: {
    margin: '0 0 10px',
    fontSize: '28px',
    color: '#333'
  },
  wordContainer: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    gap: '10px',
    fontSize: '18px'
  },
  wordLabel: {
    color: '#666',
    fontWeight: 500
  },
  word: {
    fontSize: '28px',
    fontWeight: 'bold',
    color: '#2563eb',
    textTransform: 'capitalize'
  },
  canvasWrapper: {
    background: '#fff',
    borderRadius: '12px',
    boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
    padding: '4px'
  },
  canvas: {
    borderRadius: '8px',
    cursor: 'crosshair',
    display: 'block'
  },
  results: {
    marginTop: '20px',
    padding: '16px',
    background: '#fff',
    borderRadius: '12px',
    boxShadow: '0 2px 10px rgba(0,0,0,0.08)',
    width: '100%',
    maxWidth: '360px'
  },
  resultsTitle: {
    margin: '0 0 12px',
    fontSize: '16px',
    color: '#333'
  },
  predictions: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px'
  },
  prediction: {
    display: 'flex',
    alignItems: 'center',
    padding: '10px 12px',
    background: '#f8fafc',
    borderRadius: '8px',
    gap: '12px'
  },
  rank: {
    width: '30px',
    fontWeight: 'bold',
    color: '#64748b',
    fontSize: '14px'
  },
  label: {
    flex: 1,
    fontSize: '16px',
    color: '#1e293b',
    textTransform: 'capitalize'
  },
  confidence: {
    fontSize: '14px',
    color: '#64748b',
    fontWeight: 500
  },
  correct: {
    marginTop: '16px',
    padding: '12px',
    background: '#dcfce7',
    color: '#166534',
    borderRadius: '8px',
    textAlign: 'center',
    fontWeight: 600
  },
  controls: {
    display: 'flex',
    gap: '12px',
    marginTop: '20px',
    width: '100%',
    maxWidth: '360px',
    justifyContent: 'center'
  },
  button: {
    flex: 1,
    padding: '12px 24px',
    fontSize: '16px',
    fontWeight: 600,
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    background: '#2563eb',
    color: '#fff',
    transition: 'background 0.2s'
  },
  clearButton: {
    background: '#ef4444'
  },
  hint: {
    marginTop: '20px',
    fontSize: '14px',
    color: '#64748b',
    textAlign: 'center'
  }
};