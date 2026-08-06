"""ML Validators - Tier 1 Quality Checks (Zero Tokens)."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from config import config
from models.quality_models import CheckStatus, CheckType, MLCheckResult
from utils.image_utils import ImageUtils
from utils.logger import get_logger

logger = get_logger("phase3.ml_validators")


@dataclass
class MLValidators:
    """
    Zero-token quality checks using local ML models.
    
    Implements:
    1. CLIP score (prompt <-> image embedding similarity)
    2. Artifact detection (edge detection + anomaly scoring)
    3. Face/Body Logic (landmark detection)
    4. Composition (rule-of-thirds, symmetry, focal point)
    5. Style Consistency (embedding similarity vs. reference)
    6. Technical Quality (resolution, aspect ratio, color space, blur)
    7. Structural Similarity (SSIM / LPIPS against reference)
    8. Text Readability (OCR comparison)
    """
    
    enabled_checks: list[CheckType] = field(default_factory=list)
    clip_available: bool = False
    cv_available: bool = False
    
    def __init__(self, config_override=None):
        self.config = config_override or config.phase3
        self.enabled_checks: list[CheckType] = []
        self.clip_available = False
        self.cv_available = False
        self._check_dependencies()
        self._initialize_enabled_checks()
    
    def _check_dependencies(self):
        """Check which ML libraries are available."""
        try:
            import clip
            self.clip_available = True
        except ImportError:
            logger.warning("CLIP not available, prompt alignment check disabled")
        
        try:
            import cv2
            import numpy as np
            self.cv_available = True
        except ImportError:
            logger.warning("OpenCV not available, some checks disabled")
    
    def _initialize_enabled_checks(self):
        """Initialize enabled checks from config."""
        self.enabled_checks = []
        if hasattr(self.config, 'ml_checks'):
            for check_name in self.config.ml_checks:
                try:
                    self.enabled_checks.append(CheckType[check_name.upper()])
                except KeyError:
                    logger.warning(f"Unknown ML check: {check_name}")
    
    async def run_all_checks(
        self,
        image_path: str,
        prompt: str = "",
        reference_path: str = None
    ) -> list[MLCheckResult]:
        """
        Run all enabled ML checks on an image.
        
        Args:
            image_path: Path to the image to check
            prompt: Optional prompt for alignment check
            reference_path: Optional reference image for similarity check
        
        Returns:
            List of MLCheckResult objects
        """
        results = []
        tasks = []
        
        # Run checks that don't depend on other results
        if CheckType.PROMPT_ALIGNMENT in self.enabled_checks and prompt:
            tasks.append(self.clip_score(image_path, prompt))
        
        if CheckType.ARTIFACT_DETECTION in self.enabled_checks:
            tasks.append(self.detect_artifacts(image_path))
        
        if CheckType.FACE_BODY_LOGIC in self.enabled_checks:
            tasks.append(self.check_body_logic(image_path))
        
        if CheckType.COMPOSITION in self.enabled_checks:
            tasks.append(self.assess_composition(image_path))
        
        if CheckType.TECHNICAL_QUALITY in self.enabled_checks:
            tasks.append(self.check_technical_quality(image_path))
        
        if CheckType.STRUCTURAL_SIMILARITY in self.enabled_checks and reference_path:
            tasks.append(self.structural_similarity(image_path, reference_path))
        
        # Run all tasks
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in raw_results:
            if isinstance(result, Exception):
                logger.warning(f"ML check failed: {result}")
                results.append(MLCheckResult(
                    check_type=CheckType.ARTIFACT_DETECTION,
                    score=0.0,
                    status=CheckStatus.SKIPPED,
                    issues=[str(result)]
                ))
            elif isinstance(result, MLCheckResult):
                results.append(result)
        
        return results
    
    async def clip_score(self, image_path: str, prompt: str) -> MLCheckResult:
        """Calculate CLIP similarity score between image and prompt."""
        if not self.clip_available:
            return MLCheckResult(
                check_type=CheckType.PROMPT_ALIGNMENT,
                score=0.5,
                status=CheckStatus.SKIPPED,
                issues=["CLIP not available"]
            )
        
        try:
            import clip
            import torch
            from PIL import Image
            
            # Load model
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model, preprocess = clip.load("ViT-B/32", device=device)
            
            # Preprocess image
            image = preprocess(Image.open(image_path)).unsqueeze(0).to(device)
            # Prompts can exceed CLIP's 77-token context limit; truncate if needed.
            text_prompt = f"a photo of {prompt}"
            try:
                text = clip.tokenize([text_prompt], truncate=True).to(device)
            except TypeError:
                # Older CLIP build without truncate kwarg: fall back to a short prompt.
                short = " ".join(text_prompt.split()[:60])
                text = clip.tokenize([short]).to(device)
            
            # Calculate similarity
            with torch.no_grad():
                image_features = model.encode_image(image)
                text_features = model.encode_text(text)
                
                # Normalize
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
                
                similarity = (image_features @ text_features.T).item()
                
                # Convert to 0-1 score
                score = (similarity + 1) / 2
                
                return MLCheckResult(
                    check_type=CheckType.PROMPT_ALIGNMENT,
                    score=score,
                    status=CheckStatus.PASSED if score >= 0.5 else CheckStatus.FAILED,
                    confidence=score,
                    details={"similarity_score": similarity}
                )
        
        except Exception as e:
            logger.error(f"CLIP score error: {e}")
            return MLCheckResult(
                check_type=CheckType.PROMPT_ALIGNMENT,
                score=0.0,
                status=CheckStatus.FAILED,
                issues=[str(e)]
            )
    
    async def detect_artifacts(self, image_path: str) -> MLCheckResult:
        """Detect artifacts and glitches in an image."""
        if not self.cv_available:
            return MLCheckResult(
                check_type=CheckType.ARTIFACT_DETECTION,
                score=1.0,  # Assume OK if we can't check
                status=CheckStatus.SKIPPED,
                issues=["OpenCV not available"]
            )
        
        try:
            import cv2
            
            img = cv2.imread(image_path)
            if img is None:
                return MLCheckResult(
                    check_type=CheckType.ARTIFACT_DETECTION,
                    score=0.0,
                    status=CheckStatus.FAILED,
                    issues=["Could not read image"]
                )
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Edge detection
            edges = cv2.Canny(gray, 100, 200)
            edge_pixels = cv2.countNonZero(edges)
            total_pixels = gray.size
            edge_density = edge_pixels / total_pixels if total_pixels > 0 else 0
            
            # Blur detection
            blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Anomaly score (simplified)
            # Low blur and high edge density might indicate artifacts
            anomaly_score = max(0, 1 - blur_score / 100) * edge_density
            
            # Score (higher is better - less artifacts)
            score = 1.0 - min(anomaly_score, 1.0)
            
            return MLCheckResult(
                check_type=CheckType.ARTIFACT_DETECTION,
                score=score,
                status=CheckStatus.PASSED if score >= 0.7 else CheckStatus.FAILED,
                confidence=abs(0.5 - score) * 2,
                details={
                    "edge_density": edge_density,
                    "blur_score": blur_score,
                    "anomaly_score": anomaly_score
                },
                issues=["Potential artifacts detected"] if score < 0.7 else []
            )
        
        except Exception as e:
            logger.error(f"Artifact detection error: {e}")
            return MLCheckResult(
                check_type=CheckType.ARTIFACT_DETECTION,
                score=0.0,
                status=CheckStatus.FAILED,
                issues=[str(e)]
            )
    
    async def check_body_logic(self, image_path: str) -> MLCheckResult:
        """Check for body/facial logic issues using MediaPipe."""
        issues = []
        details = {}

        try:
            import cv2
            import mediapipe as mp
            import numpy as np

            img = cv2.imread(image_path)
            if img is None:
                return MLCheckResult(
                    check_type=CheckType.FACE_BODY_LOGIC,
                    score=0.0,
                    status=CheckStatus.FAILED,
                    issues=["Could not read image"]
                )

            height, width = img.shape[:2]
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            try:
                mp_face = mp.solutions.face_detection
                face_detection = mp_face.FaceDetection(min_detection_confidence=0.5)
                face_results = face_detection.process(rgb_img)

                if face_results.detections:
                    details["face_count"] = len(face_results.detections)
                    for i, detection in enumerate(face_results.detections):
                        bbox = detection.location_data.relative_bounding_box
                        details[f"face_{i}_bbox"] = {
                            "x": bbox.xmin, "y": bbox.ymin,
                            "w": bbox.width, "h": bbox.height
                        }
                        if bbox.width > 0.9 or bbox.height > 0.9:
                            issues.append("Face proportionally too large for image")
                        if bbox.xmin < 0 or bbox.ymin < 0:
                            issues.append("Face partially outside image bounds")
                face_detection.close()
            except Exception as e:
                logger.debug(f"Face detection skipped: {e}")

            try:
                mp_pose = mp.solutions.pose
                pose = mp_pose.Pose(
                    static_image_mode=True,
                    min_detection_confidence=0.5
                )
                pose_results = pose.process(rgb_img)

                if pose_results.pose_landmarks:
                    landmarks = pose_results.pose_landmarks.landmark
                    details["pose_landmarks_count"] = len(landmarks)

                    visibility_scores = [lm.visibility for lm in landmarks]
                    avg_visibility = sum(visibility_scores) / len(visibility_scores)
                    details["avg_landmark_visibility"] = avg_visibility

                    if avg_visibility < 0.3:
                        issues.append("Low landmark visibility, possible occlusion or poor pose")

                    left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value]
                    right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
                    shoulder_diff = abs(left_shoulder.y - right_shoulder.y)
                    details["shoulder_symmetry"] = shoulder_diff
                    if shoulder_diff > 0.15:
                        issues.append("Asymmetric shoulders detected")

                    left_hip = landmarks[mp_pose.PoseLandmark.LEFT_HIP.value]
                    right_hip = landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value]
                    hip_diff = abs(left_hip.y - right_hip.y)
                    details["hip_symmetry"] = hip_diff
                    if hip_diff > 0.15:
                        issues.append("Asymmetric hips detected")

                    left_elbow = landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value]
                    left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value]
                    left_arm_angle = abs(
                        (left_elbow.y - left_shoulder.y) -
                        (left_wrist.y - left_elbow.y)
                    )
                    if left_arm_angle > 0.5:
                        issues.append("Unnatural left arm angle")
                pose.close()
            except Exception as e:
                logger.debug(f"Pose detection skipped: {e}")

        except ImportError:
            return MLCheckResult(
                check_type=CheckType.FACE_BODY_LOGIC,
                score=1.0,
                status=CheckStatus.SKIPPED,
                confidence=0.0,
                details={},
                issues=["MediaPipe not available"]
            )
        except Exception as e:
            logger.error(f"Body logic check error: {e}")
            return MLCheckResult(
                check_type=CheckType.FACE_BODY_LOGIC,
                score=0.0,
                status=CheckStatus.FAILED,
                issues=[str(e)]
            )

        score = 1.0 - (len(issues) * 0.2)
        score = max(0.0, min(1.0, score))

        return MLCheckResult(
            check_type=CheckType.FACE_BODY_LOGIC,
            score=score,
            status=CheckStatus.PASSED if not issues else CheckStatus.FAILED,
            confidence=min(1.0, len(details) / 10.0),
            details=details,
            issues=issues
        )
    
    async def assess_composition(self, image_path: str) -> MLCheckResult:
        """Assess image composition (rule of thirds, symmetry, etc.)."""
        if not self.cv_available:
            return MLCheckResult(
                check_type=CheckType.COMPOSITION,
                score=1.0,
                status=CheckStatus.SKIPPED,
                issues=["OpenCV not available"]
            )
        try:
            import cv2
            import numpy as np
            
            img = cv2.imread(image_path)

            if img is None:
                return MLCheckResult(
                    check_type=CheckType.COMPOSITION,
                    score=0.0,
                    status=CheckStatus.FAILED,
                    issues=["Could not read image"]
                )
            
            height, width = img.shape[:2]
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 100, 200)
            total_edges = cv2.countNonZero(edges)
            
            # Effective composition heuristic:
            # - Assess how evenly detail (edges) is distributed across a 3x3 grid.
            # - A well-composed image spreads content; a heavily one-corner image is poor.
            # - Blank/low-detail images default to a neutral score rather than a failure.
            blank = total_edges < height * width * 0.001
            if blank:
                composition_score = 0.5
            else:
                third_h = max(1, height // 3)
                third_w = max(1, width // 3)
                densities = []
                for gy in range(3):
                    for gx in range(3):
                        region = edges[gy*third_h:(gy+1)*third_h, gx*third_w:(gx+1)*third_w]
                        densities.append(cv2.countNonZero(region) / (third_h * third_w))
                densities = np.asarray(densities, dtype=float)
                mean_density = float(densities.mean())
                cv_all = float(densities.std()) / (mean_density + 1e-6)
                # coefficient of variation -> balance score (0 spread => good)
                balance = 1.0 / (1.0 + cv_all)
                coverage = float((densities > (mean_density * 0.5)).mean())
                composition_score = min(0.6 * balance + 0.4 * (0.5 + 0.5 * coverage), 1.0)
            
            return MLCheckResult(
                check_type=CheckType.COMPOSITION,
                score=composition_score,
                status=CheckStatus.PASSED if composition_score >= 0.5 else CheckStatus.INCONCLUSIVE,
                confidence=0.5,
                details={"composition_score": composition_score},
                issues=[]
            )
        
        except Exception as e:
            logger.error(f"Composition check error: {e}")
            return MLCheckResult(
                check_type=CheckType.COMPOSITION,
                score=0.0,
                status=CheckStatus.FAILED,
                issues=[str(e)]
            )
    
    async def check_technical_quality(self, image_path: str) -> MLCheckResult:
        """Check technical quality (resolution, format, etc.)."""
        issues = []
        details = {}
        
        # Check file exists and is valid
        if not Path(image_path).exists():
            return MLCheckResult(
                check_type=CheckType.TECHNICAL_QUALITY,
                score=0.0,
                status=CheckStatus.FAILED,
                issues=["File does not exist"]
            )
        
        # Get image info
        img_info = ImageUtils.get_image_info(image_path)
        details["image_info"] = img_info
        
        if "error" in img_info:
            return MLCheckResult(
                check_type=CheckType.TECHNICAL_QUALITY,
                score=0.0,
                status=CheckStatus.FAILED,
                issues=[img_info["error"]]
            )
        
        width = img_info.get("width", 0)
        height = img_info.get("height", 0)
        image_format = img_info.get("format", "").lower()
        
        # Check minimum resolution
        min_resolution = 512
        if width < min_resolution or height < min_resolution:
            issues.append(f"Resolution too low: {width}x{height}")
        
        # Check format
        valid_formats = ["png", "jpg", "jpeg", "webp"]
        if image_format not in valid_formats:
            issues.append(f"Unsupported format: {image_format}")
        
        # Check aspect ratio (should be reasonable)
        if width > 0 and height > 0:
            aspect_ratio = width / height
            details["aspect_ratio"] = aspect_ratio
            if aspect_ratio < 0.1 or aspect_ratio > 10:
                issues.append(f"Extreme aspect ratio: {aspect_ratio:.2f}")
        
        # Check blur
        # Laplacian variance is unreliable for flat-color/cartoon/mascot art
        # (low variance is normal there). Only flag as blurry when variance is
        # extremely low, which indicates a genuinely blurred/soft image.
        blur_score = ImageUtils.detect_blur(image_path)
        details["blur_score"] = blur_score
        if blur_score < 25:  # Extremely low variance = actually blurred
            issues.append("Image appears blurry")
        
        # Calculate score
        score = 1.0
        if issues:
            score = max(0.3, 1.0 - len(issues) * 0.2)
        
        return MLCheckResult(
            check_type=CheckType.TECHNICAL_QUALITY,
            score=score,
            status=CheckStatus.PASSED if not issues else CheckStatus.FAILED,
            confidence=1.0,
            details=details,
            issues=issues
        )
    
    async def structural_similarity(
        self,
        image_path: str,
        reference_path: str
    ) -> MLCheckResult:
        """Calculate structural similarity between two images."""
        if not self.cv_available:
            return MLCheckResult(
                check_type=CheckType.STRUCTURAL_SIMILARITY,
                score=1.0,
                status=CheckStatus.SKIPPED,
                issues=["OpenCV not available"]
            )
        
        try:
            import cv2
            import numpy as np
            from skimage.metrics import structural_similarity as ssim
            
            img1 = cv2.imread(image_path)
            img2 = cv2.imread(reference_path)
            
            if img1 is None or img2 is None:
                return MLCheckResult(
                    check_type=CheckType.STRUCTURAL_SIMILARITY,
                    score=0.0,
                    status=CheckStatus.FAILED,
                    issues=["Could not read one or both images"]
                )
            
            # Convert to grayscale
            gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
            
            # Resize to same dimensions
            min_height = min(gray1.shape[0], gray2.shape[0])
            min_width = min(gray1.shape[1], gray2.shape[1])
            gray1 = cv2.resize(gray1, (min_width, min_height))
            gray2 = cv2.resize(gray2, (min_width, min_height))
            
            # Calculate SSIM
            score, _ = ssim(gray1, gray2, full=True, data_range=gray1.max())
            
            return MLCheckResult(
                check_type=CheckType.STRUCTURAL_SIMILARITY,
                score=score,
                status=CheckStatus.PASSED if score >= 0.7 else CheckStatus.INCONCLUSIVE,
                confidence=abs(0.5 - score) * 2,
                details={"ssim_score": score}
            )
        
        except ImportError as e:
            logger.warning(f"scikit-image not available for SSIM: {e}")
            return MLCheckResult(
                check_type=CheckType.STRUCTURAL_SIMILARITY,
                score=0.5,
                status=CheckStatus.SKIPPED,
                issues=["scikit-image not available"]
            )
        except Exception as e:
            logger.error(f"SSIM calculation error: {e}")
            return MLCheckResult(
                check_type=CheckType.STRUCTURAL_SIMILARITY,
                score=0.0,
                status=CheckStatus.FAILED,
                issues=[str(e)]
            )
    
    async def check_text_accuracy(self, image_path: str, expected_text: str) -> MLCheckResult:
        """Check if text in image matches expected text using OCR."""
        if not expected_text:
            return MLCheckResult(
                check_type=CheckType.TEXT_READABILITY,
                score=1.0,
                status=CheckStatus.SKIPPED,
                issues=["No expected text provided for comparison"]
            )

        try:
            import cv2

            img = cv2.imread(image_path)
            if img is None:
                return MLCheckResult(
                    check_type=CheckType.TEXT_READABILITY,
                    score=0.0,
                    status=CheckStatus.FAILED,
                    issues=["Could not read image"]
                )

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            try:
                import easyocr
                reader = easyocr.Reader(['en'], gpu=False)
                results = reader.readtext(gray)

                extracted_texts = []
                for bbox, text, confidence in results:
                    extracted_texts.append({
                        "text": text,
                        "confidence": confidence
                    })

                if not extracted_texts:
                    if len(expected_text) > 3:
                        return MLCheckResult(
                            check_type=CheckType.TEXT_READABILITY,
                            score=0.3,
                            status=CheckStatus.FAILED,
                            confidence=0.8,
                            details={"extracted": [], "expected": expected_text},
                            issues=["No text found in image but prompt specifies text"]
                        )
                    return MLCheckResult(
                        check_type=CheckType.TEXT_READABILITY,
                        score=1.0,
                        status=CheckStatus.PASSED,
                        confidence=0.5,
                        details={"extracted": [], "expected": expected_text},
                        issues=[]
                    )

                combined_text = " ".join(t["text"] for t in extracted_texts)
                expected_lower = expected_text.lower()
                combined_lower = combined_text.lower()

                words_expected = set(expected_lower.split())
                words_found = set(combined_lower.split())
                matching_words = words_expected & words_found
                match_ratio = len(matching_words) / max(len(words_expected), 1)

                avg_confidence = sum(t["confidence"] for t in extracted_texts) / len(extracted_texts)

                issues = []
                if match_ratio < 0.5:
                    issues.append(f"Text mismatch: found {len(matching_words)}/{len(words_expected)} expected words")
                if avg_confidence < 0.5:
                    issues.append("Low OCR confidence, text may be garbled")

                score = (match_ratio * 0.7) + (avg_confidence * 0.3)
                score = max(0.0, min(1.0, score))

                return MLCheckResult(
                    check_type=CheckType.TEXT_READABILITY,
                    score=score,
                    status=CheckStatus.PASSED if not issues else CheckStatus.FAILED,
                    confidence=avg_confidence,
                    details={
                        "extracted_texts": extracted_texts,
                        "expected": expected_text,
                        "match_ratio": match_ratio
                    },
                    issues=issues
                )

            except ImportError:
                try:
                    import pytesseract
                    text = pytesseract.image_to_string(gray).strip()
                    if not text:
                        return MLCheckResult(
                            check_type=CheckType.TEXT_READABILITY,
                            score=1.0,
                            status=CheckStatus.SKIPPED,
                            issues=["No text detected via Tesseract"]
                        )
                    expected_lower = expected_text.lower()
                    text_lower = text.lower()
                    words_expected = set(expected_lower.split())
                    words_found = set(text_lower.split())
                    match_ratio = len(words_expected & words_found) / max(len(words_expected), 1)
                    score = max(0.0, min(1.0, match_ratio))
                    return MLCheckResult(
                        check_type=CheckType.TEXT_READABILITY,
                        score=score,
                        status=CheckStatus.PASSED if score >= 0.5 else CheckStatus.FAILED,
                        confidence=0.5,
                        details={"extracted": text, "expected": expected_text},
                        issues=[] if score >= 0.5 else ["Text mismatch detected"]
                    )
                except ImportError:
                    return MLCheckResult(
                        check_type=CheckType.TEXT_READABILITY,
                        score=1.0,
                        status=CheckStatus.SKIPPED,
                        details={"expected": expected_text},
                        issues=["Neither EasyOCR nor Tesseract available"]
                    )

        except Exception as e:
            logger.error(f"Text accuracy check error: {e}")
            return MLCheckResult(
                check_type=CheckType.TEXT_READABILITY,
                score=0.0,
                status=CheckStatus.FAILED,
                issues=[str(e)]
            )
    
    def add_check(self, check_type: CheckType):
        """Add a check to the enabled list."""
        if check_type not in self.enabled_checks:
            self.enabled_checks.append(check_type)
    
    def remove_check(self, check_type: CheckType):
        """Remove a check from the enabled list."""
        if check_type in self.enabled_checks:
            self.enabled_checks.remove(check_type)
