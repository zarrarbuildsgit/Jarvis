// JARVIS UI Server - Express.js
import express from 'express';
import { createServer } from 'http';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';

const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(helmet());
app.use(morgan('dev'));
app.use(express.json());

const server = createServer(app);

// Health check
app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Serve static frontend
app.use(express.static('frontend/build'));

server.listen(PORT, () => {
  console.log(`JARVIS UI Server running on http://localhost:${PORT}`);
});
