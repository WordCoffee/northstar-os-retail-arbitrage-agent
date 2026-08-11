import { useState, useEffect, useCallback } from 'react';
import * as tf from '@tensorflow/tfjs';
import DrawingCanvas from './DrawingCanvas';

const MODEL_URL = 'https://storage.googleapis.com/tfjs-models/quickdraw/model.json';

const CLASS_NAMES = [
  "airplane", "alarm clock", "ambulance", "angel", "animal migration", "ant", "anvil", "apple", "arm", "asparagus",
  "axe", "backpack", "banana", "bandage", "barn", "baseball", "baseball bat", "basket", "basketball", "bat",
  "bathtub", "beach", "bear", "beard", "bed", "bee", "belt", "bench", "bicycle", "binoculars",
  "bird", "birthday cake", "blackberry", "blueberry", "book", "boomerang", "bottlecap", "bowtie", "bracelet", "brain",
  "bread", "bridge", "broccoli", "broom", "bucket", "bulldozer", "bus", "bush", "butterfly", "cactus",
  "cake", "calculator", "calendar", "camel", "camera", "camouflage", "campfire", "candle", "cannon", "canoe",
  "car", "carrot", "castle", "cat", "ceiling fan", "cello", "cell phone", "chair", "chandelier", "church",
  "circle", "clarinet", "clock", "cloud", "coffee cup", "compass", "computer", "cookie", "cooler", "couch",
  "cow", "crab", "crayon", "crocodile", "crown", "cruise ship", "cup", "diamond", "dishwasher", "diving board",
  "dog", "dolphin", "donut", "door", "dragon", "dresser", "drill", "drums", "duck", "dumbbell",
  "ear", "elbow", "elephant", "envelope", "eraser", "eye", "eyeglasses", "face", "fan", "feather",
  "fence", "finger", "fire hydrant", "fireplace", "firetruck", "fish", "flamingo", "flashlight", "flip flops", "floor lamp",
  "flower", "flying saucer", "foot", "fork", "frog", "frying pan", "garden", "garden hose", "giraffe", "goatee",
  "golf club", "grapes", "grass", "guitar", "hamburger", "hammer", "hand", "harp", "hat", "headphones",
  "hedgehog", "helicopter", "helmet", "hexagon", "hockey puck", "hockey stick", "horse", "hospital", "hot air balloon", "hot dog",
  "hot tub", "hourglass", "house", "house plant", "hurricane", "ice cream", "jacket", "jail", "kangaroo", "key",
  "keyboard", "knee", "knife", "ladder", "lantern", "laptop", "leaf", "leg", "light bulb", "lighter",
  "lighthouse", "lightning", "line", "lion", "lipstick", "lobster", "lollipop", "mailbox", "map", "marker",
  "matches", "megaphone", "mermaid", "microphone", "microwave", "monkey", "moon", "mosquito", "motorbike", "mountain",
  "mouse", "moustache", "mouth", "mug", "mushroom", "nail", "necklace", "nose", "ocean", "octagon",
  "octopus", "onion", "oven", "owl", "paintbrush", "paint can", "palm tree", "panda", "pants", "paper clip",
  "parachute", "parrot", "passport", "peanut", "pear", "peas", "pencil", "penguin", "piano", "pickup truck",
  "picture frame", "pig", "pillow", "pineapple", "pizza", "pliers", "police car", "pond", "pool", "popsicle",
  "postcard", "potato", "power outlet", "purse", "rabbit", "raccoon", "radio", "rain", "rainbow", "rake",
  "remote control", "rhinoceros", "river", "roller coaster", "rollerskates", "sailboat", "sandwich", "saw", "saxophone", "school bus",
  "scissors", "scorpion", "screwdriver", "sea turtle", "see saw", "shark", "sheep", "shoe", "shorts", "shovel",
  "sink", "skateboard", "skull", "skyscraper", "sleeping bag", "smiley face", "snail", "snake", "snorkel", "snowflake",
  "snowman", "soccer ball", "sock", "speedboat", "spider", "spoon", "spreadsheet", "square", "squiggle", "squirrel",
  "stairs", "star", "steak", "stereo", "stethoscope", "stitches", "stop sign", "stove", "strawberry", "streetlight",
  "string bean", "submarine", "suitcase", "sun", "swan", "sweater", "swing set", "sword", "syringe", "table",
  "teapot", "teddy-bear", "telephone", "television", "tennis racquet", "tent", "the Eiffel Tower", "the Great Wall of China", "the Mona Lisa", "tiger",
  "toaster", "toe", "toilet", "tooth", "toothbrush", "toothpaste", "tornado", "tractor", "traffic light", "train",
  "tree", "triangle", "trombone", "truck", "trumpet", "t-shirt", "umbrella", "underwear", "van", "vase",
  "violin", "washing machine", "watermelon", "waterslide", "whale", "wheel", "windmill", "wine bottle", "wine glass", "wristwatch",
  "yoga", "zebra", "zigzag"
];

const MODEL_INPUT_SIZE = 28;

function App() {
  const [model, setModel] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [classNames] = useState(CLASS_NAMES);

  useEffect(() => {
    loadModel();
  }, []);

  const loadModel = async () => {
    try {
      setLoading(true);
      setError(null);
      const loadedModel = await tf.loadGraphModel(MODEL_URL);
      setModel(loadedModel);
    } catch (err) {
      console.error('Error loading model:', err);
      setError('Failed to load AI model. Please check your connection and refresh.');
    } finally {
      setLoading(false);
    }
  };

  const preprocessCanvas = useCallback((canvas) => {
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = MODEL_INPUT_SIZE;
    tempCanvas.height = MODEL_INPUT_SIZE;
    const tempCtx = tempCanvas.getContext('2d');
    tempCtx.drawImage(canvas, 0, 0, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE);
    const imageData = tempCtx.getImageData(0, 0, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE);
    const values = new Float32Array(MODEL_INPUT_SIZE * MODEL_INPUT_SIZE);
    for (let i = 0; i < MODEL_INPUT_SIZE * MODEL_INPUT_SIZE; i++) {
      const alpha = imageData.data[i * 4 + 3];
      values[i] = alpha / 255;
    }
    return tf.tensor4d(values, [1, MODEL_INPUT_SIZE, MODEL_INPUT_SIZE, 1]);
  }, []);

  const predict = useCallback(async (canvas) => {
    if (!model) return [];
    
    const tensor = preprocessCanvas(canvas);
    const prediction = await model.predict(tensor).data();
    tensor.dispose();
    
    const top5 = Array.from(prediction)
      .map((prob, idx) => ({ className: classNames[idx], probability: prob }))
      .sort((a, b) => b.probability - a.probability)
      .slice(0, 5);
    
    return top5;
  }, [model, classNames, preprocessCanvas]);

  if (loading) {
    return (
      <div style={styles.loadingContainer}>
        <div style={styles.spinner}></div>
        <p style={styles.loadingText}>Loading AI model...</p>
        <p style={styles.loadingSubtext}>Loading Google QuickDraw model (345 classes)</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.errorContainer}>
        <h2 style={styles.errorTitle}>Error Loading Model</h2>
        <p style={styles.errorText}>{error}</p>
        <button onClick={loadModel} style={styles.retryButton}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div style={styles.app}>
      <DrawingCanvas 
        onPredict={predict} 
        isPredicting={false}
        classNames={classNames}
      />
    </div>
  );
}

const styles = {
  app: {
    minHeight: '100vh',
    background: '#f5f5f5'
  },
  loadingContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    background: '#f5f5f5',
    fontFamily: 'system-ui, sans-serif'
  },
  spinner: {
    width: '48px',
    height: '48px',
    border: '4px solid #e2e8f0',
    borderTopColor: '#2563eb',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
    marginBottom: '16px'
  },
  loadingText: {
    margin: '0 0 8px',
    fontSize: '18px',
    color: '#333'
  },
  loadingSubtext: {
    margin: 0,
    fontSize: '14px',
    color: '#64748b'
  },
  errorContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    background: '#f5f5f5',
    fontFamily: 'system-ui, sans-serif',
    padding: '20px',
    textAlign: 'center'
  },
  errorTitle: {
    margin: '0 0 12px',
    color: '#ef4444'
  },
  errorText: {
    margin: '0 0 20px',
    color: '#64748b'
  },
  retryButton: {
    padding: '12px 24px',
    fontSize: '16px',
    fontWeight: 600,
    border: 'none',
    borderRadius: '8px',
    cursor: 'pointer',
    background: '#2563eb',
    color: '#fff'
  }
};

export default App;