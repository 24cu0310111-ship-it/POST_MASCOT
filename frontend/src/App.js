import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  TextField,
  Button,
  Card,
  CardContent,
  Grid,
  CircularProgress,
  Alert,
  Snackbar,
  Divider,
  Chip,
  Paper,
  Stack,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tabs,
  Tab,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  FormControlLabel,
  List,
  ListItem,
  ListItemText,
  IconButton,
} from '@mui/material';
import {
  Send as SendIcon,
  CloudUpload as UploadIcon,
  Download as DownloadIcon,
  Settings as SettingsIcon,
  Info as InfoIcon,
  History as HistoryIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckCircleIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Image as ImageIcon,
} from '@mui/icons-material';
import axios from 'axios';
import { v4 as uuidv4 } from 'uuid';

// API configuration
const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

function App() {
  const [activeTab, setActiveTab] = useState(0);
  const [prompt, setPrompt] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [results, setResults] = useState([]);
  const [currentTaskId, setCurrentTaskId] = useState(null);
  const [analyzedInput, setAnalyzedInput] = useState(null);
  const [clarificationQuestions, setClarificationQuestions] = useState([]);
  const [clarificationResponses, setClarificationResponses] = useState({});
  const [needsClarification, setNeedsClarification] = useState(false);
  const [backend, setBackend] = useState('mcp');
  const [maxIterations, setMaxIterations] = useState(3);
  const [autoRefine, setAutoRefine] = useState(true);
  const [history, setHistory] = useState([]);
  const [status, setStatus] = useState(null);
  const [backendStatus, setBackendStatus] = useState(null);

  // Snackbar state
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');
  const [snackbarSeverity, setSnackbarSeverity] = useState('info');

  // Dialog states
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [imagePreviewOpen, setImagePreviewOpen] = useState(false);
  const [selectedImage, setSelectedImage] = useState(null);

  // Reference files
  const [referenceFiles, setReferenceFiles] = useState([]);

  // Load history on startup
  useEffect(() => {
    const savedHistory = localStorage.getItem('mao_history');
    if (savedHistory) {
      setHistory(JSON.parse(savedHistory));
    }
    
    // Check API status
    const checkApi = async () => {
      try {
        const response = await axios.get(`${API_BASE}/health`);
        setStatus(response.data);
        showSnackbar('API is ready', 'success');
      } catch (error) {
        setStatus({ error: 'API not available' });
        showSnackbar('API connection failed', 'error');
      }
    };
    checkApi();
    checkBackendStatus();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Save history when it changes
  useEffect(() => {
    localStorage.setItem('mao_history', JSON.stringify(history));
  }, [history]);

  const showSnackbar = (message, severity = 'info') => {
    setSnackbarMessage(message);
    setSnackbarSeverity(severity);
    setSnackbarOpen(true);
  };

  const checkBackendStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE}/backends`);
      setBackendStatus(response.data);
    } catch (error) {
      console.error('Failed to check backend status:', error);
    }
  };

  const handleAnalyze = async () => {
    if (!prompt.trim()) {
      showSnackbar('Please enter a prompt', 'warning');
      return;
    }

    setIsAnalyzing(true);
    
    try {
      const response = await axios.post(`${API_BASE}/analyze`, {
        prompt: prompt,
        references: referenceFiles.map(f => ({ type: 'file', path: f.url })),
      });

      const data = response.data;
      
      if (data.needs_clarification) {
        setAnalyzedInput(data.analyzed_input);
        setClarificationQuestions(data.clarification.questions || []);
        setNeedsClarification(true);
        showSnackbar('Input needs clarification', 'warning');
      } else {
        setAnalyzedInput(data.analyzed_input);
        setNeedsClarification(false);
        showSnackbar('Input analysis complete', 'success');
      }
    } catch (error) {
      showSnackbar(`Analysis failed: ${error.response?.data?.detail || error.message}`, 'error');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      showSnackbar('Please enter a prompt', 'warning');
      return;
    }

    setIsGenerating(true);
    setResults([]);
    
    const taskId = uuidv4();
    setCurrentTaskId(taskId);

    try {
      const response = await axios.post(`${API_BASE}/generate`, {
        prompt: needsClarification ? buildEnhancedPrompt() : prompt,
        references: referenceFiles.map(f => ({ type: 'file', path: f.url })),
        max_iterations: maxIterations,
        backend: backend,
      });

      const data = response.data;
      
      if (data.success) {
        // Add to history
        const historyItem = {
          id: taskId,
          prompt: prompt,
          result: data.data,
          timestamp: new Date().toISOString(),
        };
        setHistory([historyItem, ...history.slice(0, 9)]);
        
        setResults([data.data]);
        setNeedsClarification(false);
        showSnackbar('Generation completed successfully!', 'success');
      } else {
        showSnackbar(data.error || 'Generation failed', 'error');
        setResults([data.data]);
      }
    } catch (error) {
      showSnackbar(`Generation failed: ${error.response?.data?.detail || error.message}`, 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSingleGenerate = async () => {
    if (!prompt.trim()) {
      showSnackbar('Please enter a prompt', 'warning');
      return;
    }

    setIsGenerating(true);
    
    try {
      const response = await axios.post(`${API_BASE}/generate-single`, {
        prompt: needsClarification ? buildEnhancedPrompt() : prompt,
        references: referenceFiles.map(f => ({ type: 'file', path: f.url })),
        backend: backend,
      });

      const data = response.data;
      
      if (data.success) {
        setResults([data.data]);
        showSnackbar('Single generation completed', 'success');
      } else {
        showSnackbar(data.error || 'Generation failed', 'error');
      }
    } catch (error) {
      showSnackbar(`Generation failed: ${error.response?.data?.detail || error.message}`, 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleGenerateVariants = async (count = 4) => {
    if (!prompt.trim()) {
      showSnackbar('Please enter a prompt', 'warning');
      return;
    }

    setIsGenerating(true);
    
    try {
      const response = await axios.post(
        `${API_BASE}/generate-variants?count=${count}`,
        {
          prompt: needsClarification ? buildEnhancedPrompt() : prompt,
          references: referenceFiles.map(f => ({ type: 'file', path: f.url })),
          backend: backend,
        }
      );

      const data = response.data;
      
      if (data.success) {
        setResults(data.all_variants);
        showSnackbar(`Generated ${count} variants`, 'success');
      } else {
        showSnackbar(data.error || 'Variant generation failed', 'error');
      }
    } catch (error) {
      showSnackbar(`Variant generation failed: ${error.response?.data?.detail || error.message}`, 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  const buildEnhancedPrompt = () => {
    let enhanced = prompt;
    for (const [key, value] of Object.entries(clarificationResponses)) {
      enhanced += ` ${key}: ${value}`;
    }
    return enhanced;
  };

  const handleClarificationResponse = (questionIndex, value) => {
    setClarificationResponses({
      ...clarificationResponses,
      [questionIndex]: value,
    });
  };

  const handleSubmitClarification = () => {
    setNeedsClarification(false);
    // The clarifications will be used when generating
  };

  const handleUploadReference = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('reference_type', 'image');

    try {
      const response = await axios.post(`${API_BASE}/upload-reference`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      const data = response.data;
      if (data.success) {
        setReferenceFiles([...referenceFiles, data]);
        showSnackbar('Reference uploaded successfully', 'success');
      } else {
        showSnackbar(data.error || 'Upload failed', 'error');
      }
    } catch (error) {
      showSnackbar(`Upload failed: ${error.response?.data?.detail || error.message}`, 'error');
    }
  };

  const handleRemoveReference = (index) => {
    const newFiles = [...referenceFiles];
    newFiles.splice(index, 1);
    setReferenceFiles(newFiles);
  };

  const handleDownloadImage = async (taskId) => {
    try {
      const response = await axios.get(`${API_BASE}/download-image/${taskId}`, {
        responseType: 'blob',
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `generation_${taskId}.png`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      showSnackbar(`Download failed: ${error.message}`, 'error');
    }
  };

  const handlePreviewImage = (imagePath) => {
    if (imagePath) {
      // Check if it's a URL or local path
      const previewUrl = imagePath.startsWith('http') 
        ? imagePath 
        : `${API_BASE}/download-image/${currentTaskId}`;
      setSelectedImage(previewUrl);
      setImagePreviewOpen(true);
    }
  };

  const handleDownloadResult = async (taskId) => {
    try {
      const response = await axios.get(`${API_BASE}/download/${taskId}`, {
        responseType: 'blob',
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `result_${taskId}.json`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      showSnackbar(`Download failed: ${error.message}`, 'error');
    }
  };

  const handleClearResults = () => {
    setResults([]);
    setCurrentTaskId(null);
    setNeedsClarification(false);
    setClarificationResponses({});
  };

  const renderResultCard = (result, index) => {
    if (!result) return null;
    
    const quality = result.quality_report || {};
    const generation = result.generation_result || {};
    
    return (
      <Card key={index} sx={{ mb: 2 }}>
        <CardContent>
          <Grid container spacing={2}>
            <Grid item xs={12} md={8}>
              <Typography variant="h6" gutterBottom>
                Result {index + 1}
              </Typography>
              
              {generation.prompt_used && (
                <Box sx={{ mb: 2, p: 1, bgcolor: 'background.paper', borderRadius: 1 }}>
                  <Typography variant="body2" color="text.secondary">
                    Prompt
                  </Typography>
                  <Typography variant="body1" sx={{ mt: 1 }}>
                    {generation.prompt_used}
                  </Typography>
                </Box>
              )}

              {quality.overall_score && (
                <Box sx={{ mb: 2 }}>
                  <Chip 
                    icon={quality.passed ? <CheckCircleIcon /> : <WarningIcon />}
                    label={`Quality: ${quality.overall_score.toFixed(2)}`}
                    color={quality.passed ? 'success' : 'warning'}
                    variant="outlined"
                  />
                </Box>
              )}

              {quality.refinement_notes && quality.refinement_notes.length > 0 && (
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Refinement Notes:
                  </Typography>
                  <List dense>
                    {quality.refinement_notes.map((note, i) => (
                      <ListItem key={i} sx={{ pl: 0 }}>
                        <ListItemText primary={note} />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              )}

              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Iterations
                  </Typography>
                  <Typography variant="body1">{result.iteration_count || 0}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Time
                  </Typography>
                  <Typography variant="body1">{result.total_time_ms || 0}ms</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Tokens
                  </Typography>
                  <Typography variant="body1">{result.total_tokens_used || 0}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Backend
                  </Typography>
                  <Typography variant="body1">{generation.backend_used || 'unknown'}</Typography>
                </Grid>
              </Grid>
            </Grid>

            <Grid item xs={12} md={4}>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {generation.image_path && (
                  <Box>
                    <Button 
                      variant="outlined"
                      startIcon={<ImageIcon />}
                      onClick={() => handlePreviewImage(generation.image_path)}
                      fullWidth
                    >
                      Preview Image
                    </Button>
                  </Box>
                )}
                
                {currentTaskId && (
                  <>
                    <Button 
                      variant="outlined"
                      startIcon={<DownloadIcon />}
                      onClick={() => handleDownloadImage(currentTaskId)}
                      fullWidth
                    >
                      Download Image
                    </Button>
                    <Button 
                      variant="outlined"
                      startIcon={<DownloadIcon />}
                      onClick={() => handleDownloadResult(currentTaskId)}
                      fullWidth
                    >
                      Download Result JSON
                    </Button>
                  </>
                )}
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>
    );
  };

  const renderClarificationDialog = () => {
    if (!needsClarification || clarificationQuestions.length === 0) return null;

    return (
      <Dialog open={needsClarification} onClose={() => setNeedsClarification(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          <Stack direction="row" spacing={1} alignItems="center">
            <InfoIcon color="primary" />
            <Typography variant="h6">Clarification Needed</Typography>
          </Stack>
        </DialogTitle>
        <DialogContent>
          <Typography paragraph>
            Your input needs some clarification to generate the best results.
          </Typography>
          
          {analyzedInput && analyzedInput.missing_fields && analyzedInput.missing_fields.length > 0 && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Missing: {analyzedInput.missing_fields.join(', ')}
            </Alert>
          )}

          <List>
            {clarificationQuestions.map((question, index) => (
              <ListItem key={index} disableGutters sx={{ mb: 2 }}>
                <TextField
                  fullWidth
                  label={`Question ${index + 1}: ${question}`}
                  variant="outlined"
                  value={clarificationResponses[index] || ''}
                  onChange={(e) => handleClarificationResponse(index, e.target.value)}
                  multiline
                  rows={2}
                />
              </ListItem>
            ))}
          </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setNeedsClarification(false)}>
            Cancel
          </Button>
          <Button 
            onClick={handleSubmitClarification}
            variant="contained"
            color="primary"
          >
            Continue
          </Button>
        </DialogActions>
      </Dialog>
    );
  };

  const renderSettingsDialog = () => (
    <Dialog open={settingsOpen} onClose={() => setSettingsOpen(false)} maxWidth="sm">
      <DialogTitle>
        <Stack direction="row" spacing={1} alignItems="center">
          <SettingsIcon color="primary" />
          <Typography variant="h6">Settings</Typography>
        </Stack>
      </DialogTitle>
      <DialogContent>
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={12}>
            <FormControl fullWidth>
              <InputLabel>Backend</InputLabel>
              <Select
                value={backend}
                label="Backend"
                onChange={(e) => setBackend(e.target.value)}
              >
                <MenuItem value="mcp">MCP (Orshot)</MenuItem>
                <MenuItem value="cli">CLI (Stable Diffusion)</MenuItem>
                <MenuItem value="web_api">Web API (DALL-E, etc.)</MenuItem>
                <MenuItem value="local">Local (Diffusers)</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Max Iterations"
              type="number"
              value={maxIterations}
              onChange={(e) => setMaxIterations(parseInt(e.target.value) || 1)}
              inputProps={{ min: 1, max: 10 }}
            />
          </Grid>

          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={autoRefine}
                  onChange={(e) => setAutoRefine(e.target.checked)}
                />
              }
              label="Auto-refine (automatically retry with improvements)"
            />
          </Grid>

          {backendStatus && (
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                Backend Status:
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap">
                {backendStatus.available.map(name => (
                  <Chip key={name} label={name} color="success" size="small" />
                ))}
                {backendStatus.backends
                  .filter(b => !b.available)
                  .map(b => (
                    <Chip key={b.name} label={b.name} color="error" size="small" />
                  ))}
              </Stack>
            </Grid>
          )}
        </Grid>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setSettingsOpen(false)}>Close</Button>
        <Button onClick={checkBackendStatus} startIcon={<RefreshIcon />}>
          Refresh
        </Button>
      </DialogActions>
    </Dialog>
  );

  const renderHistoryDialog = () => (
    <Dialog open={historyOpen} onClose={() => setHistoryOpen(false)} maxWidth="md" fullWidth>
      <DialogTitle>
        <Stack direction="row" spacing={1} alignItems="center">
          <HistoryIcon color="primary" />
          <Typography variant="h6">Generation History</Typography>
        </Stack>
      </DialogTitle>
      <DialogContent>
        {history.length === 0 ? (
          <Typography>No history yet. Generate something to see it here!</Typography>
        ) : (
          <List>
            {history.map((item, index) => (
              <ListItem key={item.id} divider={index < history.length - 1}>
                <ListItemText
                  primary={item.prompt.substring(0, 100)}
                  secondary={new Date(item.timestamp).toLocaleString()}
                />
                <IconButton edge="end" onClick={() => handleDownloadResult(item.id)}>
                  <DownloadIcon />
                </IconButton>
              </ListItem>
            ))}
          </List>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setHistoryOpen(false)}>Close</Button>
        <Button onClick={() => setHistory([])} color="error">
          Clear History
        </Button>
      </DialogActions>
    </Dialog>
  );

  const renderImagePreviewDialog = () => (
    <Dialog open={imagePreviewOpen} onClose={() => setImagePreviewOpen(false)} maxWidth="lg">
      <DialogTitle>Image Preview</DialogTitle>
      <DialogContent>
        {selectedImage && (
          <img
            src={selectedImage}
            alt="Generated"
            style={{ maxWidth: '100%', height: 'auto' }}
            onError={() => setSelectedImage(null)}
          />
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setImagePreviewOpen(false)}>Close</Button>
      </DialogActions>
    </Dialog>
  );

  // Sample prompts for India Post mascot
  const samplePrompts = [
    'Generate a mascot for India Post that represents Trust & Reliability, Public Service, Inclusivity, Indian Culture & Heritage, Digital Innovation, Friendly Personality, and Nationwide Connectivity. The mascot should be in a modern Indian cartoon style with vibrant colors, 1024x1024 resolution.',
    'Create a friendly mascot character for India Post in traditional Indian art style with elements of digital innovation and nationwide connectivity.',
    'Design a brand ambassador character for India Post in vector illustration style, wearing postal uniform with modern digital elements.',
    'Generate a welcoming character mascot for India Post with large eyes, rounded shapes, wearing khaki and red uniform, holding a letter and a QR code.',
  ];

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <Container maxWidth="xl" sx={{ py: 3 }}>
        {/* Header */}
        <Paper elevation={3} sx={{ p: 3, mb: 3, textAlign: 'center' }}>
          <Stack direction="row" spacing={2} alignItems="center" justifyContent="center">
            <Box sx={{ width: 60, height: 60, bgcolor: 'primary.main', borderRadius: 2, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <ImageIcon sx={{ fontSize: 40, color: 'white' }} />
            </Box>
            <Box>
              <Typography variant="h4" component="h1" color="primary">
                Multi-Agent Orchestrator
              </Typography>
              <Typography variant="subtitle1" color="text.secondary">
                Intelligent Image Generation with Quality Verification
              </Typography>
            </Box>
          </Stack>
          
          <Box sx={{ mt: 2 }}>
            <Tabs value={activeTab} onChange={(e, newValue) => setActiveTab(newValue)} centered>
              <Tab label="Generate" icon={<SendIcon />} iconPosition="start" />
              <Tab label="Analyze" icon={<InfoIcon />} iconPosition="start" />
              <Tab label="Settings" icon={<SettingsIcon />} iconPosition="start" />
            </Tabs>
          </Box>
        </Paper>

        {/* Main Content */}
        {activeTab === 0 && (
          <Grid container spacing={3}>
            {/* Prompt Input */}
            <Grid item xs={12} md={8}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Generation Prompt
                  </Typography>
                  
                  <TextField
                    fullWidth
                    multiline
                    rows={6}
                    variant="outlined"
                    placeholder="Describe what you want to generate..."
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    sx={{ mb: 2 }}
                    InputProps={{
                      startAdornment: (
                        <Box sx={{ mr: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                          {referenceFiles.map((file, index) => (
                            <Chip
                              key={index}
                              label={file.filename}
                              onDelete={() => handleRemoveReference(index)}
                              size="small"
                            />
                          ))}
                        </Box>
                      ),
                    }}
                  />

                  {/* Sample Prompts */}
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Sample prompts for India Post mascot:
                    </Typography>
                    <Stack direction="row" spacing={1} flexWrap="wrap">
                      {samplePrompts.map((sample, index) => (
                        <Chip
                          key={index}
                          label={`Sample ${index + 1}`}
                          onClick={() => setPrompt(sample)}
                          size="small"
                          variant="outlined"
                          sx={{ cursor: 'pointer' }}
                        />
                      ))}
                    </Stack>
                  </Box>

                  {/* Reference Upload */}
                  <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
                    <input
                      accept="image/*"
                      style={{ display: 'none' }}
                      id="reference-upload"
                      type="file"
                      onChange={handleUploadReference}
                    />
                    <label htmlFor="reference-upload">
                      <Button 
                        variant="outlined"
                        startIcon={<UploadIcon />}
                        component="span"
                      >
                        Upload Reference
                      </Button>
                    </label>
                    
                    <Typography variant="body2" color="text.secondary">
                      Upload reference images to guide the generation
                    </Typography>
                  </Box>

                  {/* Action Buttons */}
                  <Stack direction="row" spacing={2}>
                    <Button
                      variant="contained"
                      color="primary"
                      startIcon={<SendIcon />}
                      onClick={handleGenerate}
                      disabled={isGenerating || isAnalyzing}
                      size="large"
                    >
                      {isGenerating ? <CircularProgress size={24} /> : 'Generate'}
                    </Button>
                    
                    <Button
                      variant="outlined"
                      startIcon={<RefreshIcon />}
                      onClick={() => handleGenerateVariants(4)}
                      disabled={isGenerating}
                      size="large"
                    >
                      Generate 4 Variants
                    </Button>
                    
                    <Button
                      variant="text"
                      onClick={handleClearResults}
                      disabled={results.length === 0}
                      size="large"
                    >
                      Clear
                    </Button>
                  </Stack>
                </CardContent>
              </Card>
            </Grid>

            {/* Quick Actions */}
            <Grid item xs={12} md={4}>
              <Stack spacing={2}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Quick Actions
                    </Typography>
                    
                    <Button
                      variant="outlined"
                      startIcon={<SendIcon />}
                      onClick={handleSingleGenerate}
                      fullWidth
                      disabled={isGenerating}
                    >
                      Single Generation (No Refinement)
                    </Button>

                    <Divider sx={{ my: 2 }} />

                    <Button
                      variant="outlined"
                      startIcon={<HistoryIcon />}
                      onClick={() => setHistoryOpen(true)}
                      fullWidth
                    >
                      View History
                    </Button>

                    <Button
                      variant="outlined"
                      startIcon={<SettingsIcon />}
                      onClick={() => setSettingsOpen(true)}
                      fullWidth
                    >
                      Settings
                    </Button>

                    {status && (
                      <Box sx={{ mt: 2, textAlign: 'center' }}>
                        <Chip
                          icon={status.status === 'healthy' ? <CheckCircleIcon /> : <ErrorIcon />}
                          label={status.status || 'Unknown'}
                          color={status.status === 'healthy' ? 'success' : 'error'}
                        />
                      </Box>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      Statistics
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          Generations
                        </Typography>
                        <Typography variant="h5">{history.length}</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="body2" color="text.secondary">
                          References
                        </Typography>
                        <Typography variant="h5">{referenceFiles.length}</Typography>
                      </Grid>
                    </Grid>
                  </CardContent>
                </Card>
              </Stack>
            </Grid>

            {/* Results */}
            <Grid item xs={12}>
              {isGenerating && (
                <Card>
                  <CardContent sx={{ textAlign: 'center', py: 4 }}>
                    <CircularProgress size={48} />
                    <Typography variant="h6" sx={{ mt: 2 }}>
                      Generating...
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Please wait while we create your image
                    </Typography>
                  </CardContent>
                </Card>
              )}

              {isAnalyzing && (
                <Card>
                  <CardContent sx={{ textAlign: 'center', py: 4 }}>
                    <CircularProgress size={48} />
                    <Typography variant="h6" sx={{ mt: 2 }}>
                      Analyzing Input...
                    </Typography>
                  </CardContent>
                </Card>
              )}

              {results.length > 0 && (
                <Stack spacing={2}>
                  {results.map((result, index) => renderResultCard(result, index))}
                </Stack>
              )}

              {results.length === 0 && !isGenerating && !isAnalyzing && (
                <Card>
                  <CardContent sx={{ textAlign: 'center', py: 8 }}>
                    <ImageIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                    <Typography variant="h5" gutterBottom>
                      Ready to Generate
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Enter a prompt above and click Generate to start
                    </Typography>
                  </CardContent>
                </Card>
              )}
            </Grid>
          </Grid>
        )}

        {activeTab === 1 && (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Card>
                <CardContent>
                  <Typography variant="h6" gutterBottom>
                    Input Analysis
                  </Typography>
                  
                  <TextField
                    fullWidth
                    multiline
                    rows={6}
                    variant="outlined"
                    placeholder="Enter your prompt for analysis..."
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    sx={{ mb: 2 }}
                  />

                  <Button
                    variant="contained"
                    color="primary"
                    startIcon={<InfoIcon />}
                    onClick={handleAnalyze}
                    disabled={isAnalyzing}
                  >
                    {isAnalyzing ? <CircularProgress size={24} /> : 'Analyze Input'}
                  </Button>

                  {analyzedInput && (
                    <Box sx={{ mt: 3, p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
                      <Typography variant="h6" gutterBottom>
                        Analysis Results
                      </Typography>
                      
                      <Grid container spacing={2}>
                        <Grid item xs={12} md={6}>
                          <Typography variant="body2" color="text.secondary">
                            Intent
                          </Typography>
                          <Chip label={analyzedInput.intent || 'Unknown'} />
                        </Grid>
                        <Grid item xs={12} md={6}>
                          <Typography variant="body2" color="text.secondary">
                            Subject
                          </Typography>
                          <Typography variant="body1">{analyzedInput.subject || 'Not detected'}</Typography>
                        </Grid>
                        <Grid item xs={12} md={6}>
                          <Typography variant="body2" color="text.secondary">
                            Style
                          </Typography>
                          <Typography variant="body1">{analyzedInput.style || 'Not specified'}</Typography>
                        </Grid>
                        <Grid item xs={12} md={6}>
                          <Typography variant="body2" color="text.secondary">
                            Context Score
                          </Typography>
                          <Chip 
                            label={`${analyzedInput.context_score?.toFixed(2) || 0}`}
                            color={analyzedInput.context_score >= 0.7 ? 'success' : analyzedInput.context_score >= 0.5 ? 'warning' : 'error'}
                          />
                        </Grid>
                      </Grid>

                      {analyzedInput.missing_fields && analyzedInput.missing_fields.length > 0 && (
                        <Box sx={{ mt: 2 }}>
                          <Typography variant="body2" color="text.secondary" gutterBottom>
                            Missing Fields
                          </Typography>
                          <Stack direction="row" spacing={1} flexWrap="wrap">
                            {analyzedInput.missing_fields.map((field, index) => (
                              <Chip key={index} label={field} color="warning" variant="outlined" />
                            ))}
                          </Stack>
                        </Box>
                      )}
                    </Box>
                  )}

                  {needsClarification && renderClarificationDialog()}
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        )}

        {activeTab === 2 && (
          <Grid container spacing={3}>
            <Grid item xs={12}>
              <Button
                variant="contained"
                startIcon={<SettingsIcon />}
                onClick={() => setSettingsOpen(true)}
              >
                Open Settings
              </Button>
            </Grid>
          </Grid>
        )}
      </Container>

      {/* Dialogs */}
      {renderClarificationDialog()}
      {renderSettingsDialog()}
      {renderHistoryDialog()}
      {renderImagePreviewDialog()}

      {/* Snackbar */}
      <Snackbar
        open={snackbarOpen}
        autoHideDuration={6000}
        onClose={() => setSnackbarOpen(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity={snackbarSeverity}
          onClose={() => setSnackbarOpen(false)}
          sx={{ width: '100%' }}
        >
          {snackbarMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
}

export default App;
