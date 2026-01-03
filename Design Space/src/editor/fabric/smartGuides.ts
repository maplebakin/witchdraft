
import * as fabric from 'fabric';

const SNAP_THRESHOLD = 5;
const GUIDE_COLOR = 'rgba(128, 0, 128, 0.8)'; // Purple
const GUIDE_STROKE_WIDTH = 1;

let aligningLines: fabric.Line[] = [];

/**
 * Initializes smart alignment guides on the Fabric.js canvas.
 * @param canvas The fabric.Canvas instance to attach the guides to.
 */
export const initSmartGuides = (canvas: fabric.Canvas) => {

  const drawVerticalLine = (left: number) => {
    const line = new fabric.Line([left, -canvas.height, left, canvas.height * 2], {
      stroke: GUIDE_COLOR,
      strokeWidth: GUIDE_STROKE_WIDTH,
      selectable: false,
      evented: false,
    });
    aligningLines.push(line);
    canvas.add(line);
  };

  const drawHorizontalLine = (top: number) => {
    const line = new fabric.Line([-canvas.width, top, canvas.width * 2, top], {
      stroke: GUIDE_COLOR,
      strokeWidth: GUIDE_STROKE_WIDTH,
      selectable: false,
      evented: false,
    });
    aligningLines.push(line);
    canvas.add(line);
  };

  const onObjectMoving = (e: any) => {
    const activeObject = e?.target as fabric.Object | undefined;
    if (!activeObject) return;

    // Clear previous guides
    aligningLines.forEach(line => canvas.remove(line));
    aligningLines = [];
    lastSnapCoords = {}; // Reset potential snap coordinates

    const canvasObjects = canvas.getObjects().filter(obj => obj !== activeObject);
    const activeCenter = activeObject.getCenterPoint();

    // Canvas Centering Guides
    const canvasCenter = canvas.getCenter();
    // Horizontal center
    if (Math.abs(activeCenter.x - canvasCenter.left) < SNAP_THRESHOLD) {
      lastSnapCoords.x = canvasCenter.left - activeObject.width / 2;
      drawVerticalLine(canvasCenter.left);
    }
    // Vertical center
    if (Math.abs(activeCenter.y - canvasCenter.top) < SNAP_THRESHOLD) {
      lastSnapCoords.y = canvasCenter.top - activeObject.height / 2;
      drawHorizontalLine(canvasCenter.top);
    }

    // Object-to-Object Alignment
    canvasObjects.forEach((obj: fabric.Object) => {
      const objCenter = obj.getCenterPoint();
      const objBoundingRect = obj.getBoundingRect();
      const activeBoundingRect = activeObject.getBoundingRect();

      // Vertical alignment
      // Left-to-Left
      if (Math.abs(activeBoundingRect.left - objBoundingRect.left) < SNAP_THRESHOLD) {
        lastSnapCoords.x = objBoundingRect.left;
        drawVerticalLine(objBoundingRect.left);
      }
      // Right-to-Right
      if (Math.abs(activeBoundingRect.left + activeBoundingRect.width - (objBoundingRect.left + objBoundingRect.width)) < SNAP_THRESHOLD) {
        lastSnapCoords.x = objBoundingRect.left + objBoundingRect.width - activeBoundingRect.width;
        drawVerticalLine(objBoundingRect.left + objBoundingRect.width);
      }
      // Center-to-Center
      if (Math.abs(activeCenter.x - objCenter.x) < SNAP_THRESHOLD) {
        lastSnapCoords.x = objCenter.x - activeObject.width / 2;
        drawVerticalLine(objCenter.x);
      }

      // Horizontal alignment
      // Top-to-Top
      if (Math.abs(activeBoundingRect.top - objBoundingRect.top) < SNAP_THRESHOLD) {
        lastSnapCoords.y = objBoundingRect.top;
        drawHorizontalLine(objBoundingRect.top);
      }
      // Bottom-to-Bottom
      if (Math.abs(activeBoundingRect.top + activeBoundingRect.height - (objBoundingRect.top + objBoundingRect.height)) < SNAP_THRESHOLD) {
        lastSnapCoords.y = objBoundingRect.top + objBoundingRect.height - activeBoundingRect.height;
        drawHorizontalLine(objBoundingRect.top + objBoundingRect.height);
      }
      // Center-to-Center
      if (Math.abs(activeCenter.y - objCenter.y) < SNAP_THRESHOLD) {
        lastSnapCoords.y = objCenter.y - activeObject.height / 2;
        drawHorizontalLine(objCenter.y);
      }
    });

    if (Object.keys(lastSnapCoords).length > 0) {
      activeObject.set(lastSnapCoords).setCoords();
    }

    if (aligningLines.length > 0 || currentRenderRAF !== null) {
      if (currentRenderRAF) {
        cancelAnimationFrame(currentRenderRAF);
      }
      currentRenderRAF = requestAnimationFrame(() => {
        canvas.requestRenderAll();
        currentRenderRAF = null;
      });
    }
  };

  const onMovingStopped = () => {
    aligningLines.forEach(line => canvas.remove(line));
    aligningLines = [];
    canvas.requestRenderAll();
  };

  canvas.on('object:moving', onObjectMoving);
  canvas.on('mouse:up', () => {
    removeAlignLines();
    if (currentRenderRAF) {
      cancelAnimationFrame(currentRenderRAF);
      currentRenderRAF = null;
    }

    const activeObject = canvas.getActiveObject();
    if (activeObject && (lastSnapCoords.x !== undefined || lastSnapCoords.y !== undefined)) {
      const {
        x,
        y
      } = lastSnapCoords;
      const snapOptions: {
        left ? : number;
        top ? : number
      } = {};

      if (x !== undefined) {
        snapOptions.left = x;
      }
      if (y !== undefined) {
        snapOptions.top = y;
      }

      activeObject.set(snapOptions);
      activeObject.setCoords(); // Update object's bounding box
      canvas.renderAll();
    }
    lastSnapCoords = {}; // Clear snap coordinates after drop
  });
  canvas.on('object:modified', onMovingStopped); // Another event that signifies moving has stopped

  // Return a cleanup function
  return () => {
    canvas.off('object:moving', onObjectMoving);
    canvas.off('mouse:up', onMovingStopped);
    canvas.off('object:modified', onMovingStopped);
  };
};
