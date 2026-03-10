# Implementation Prompts for WitchDraft Placeholder Features

## Prompt Set #1: Multi-Project Support

**Target Files:** `hearth.py`
**Objective:** Add ability to manage multiple projects

```
Add multi-project support to WitchDraft:

1. Create a project management system that stores projects in ~/WitchDraftProjects/
2. Add project creation wizard with name, description, and initial settings
3. Implement project switching functionality with a project selector
4. Modify file paths to be relative to the current project directory
5. Add project-specific configuration settings
6. Create project import/export functionality
7. Implement project templates for different writing types
8. Add project dashboard showing all projects and their status
9. Create project backup and sync functionality
10. Add project-specific settings for themes, palettes, and archetypes
```

## Prompt Set #2: Dark/Light Theme Options

**Target Files:** `hearth.py`
**Objective:** Add theme switching functionality

```
Add dark/light theme options to the WitchDraft interface:

1. Create theme configuration system with multiple color schemes
2. Add DARK_THEME and LIGHT_THEME constant dictionaries
3. Implement theme switching with a keyboard shortcut (Ctrl+Shift+T)
4. Add theme preference persistence using a config file
5. Create theme preview functionality
6. Add system preference detection (follows OS theme)
7. Ensure all UI elements adapt to the selected theme
8. Add contrast validation to ensure readability in all themes
9. Create custom color picker for personalized themes
10. Add theme import/export functionality for sharing themes
```

## Prompt Set #3: Advanced Visualization Options

**Target Files:** `hearth.py`
**Objective:** Add alternative graph layouts and visualization features

```
Add alternative visualization options beyond the spiral timeline:

1. Implement force-directed graph layout option for the timeline
2. Create hierarchical tree view for chapter/section organization
3. Add network graph view showing character relationships
4. Implement timeline view showing chronological order
5. Add plot structure visualization (three-act, hero's journey, etc.)
6. Create character appearance timeline showing when characters appear
7. Add scene connection strength visualization
8. Implement filtering options for the visualization (by theme, character, mood)
9. Add zoom and pan functionality to all visualizations
10. Create export functionality for visualization as image
```

## Prompt Set #4: Character Development Tools

**Target Files:** `hearth.py`
**Objective:** Add comprehensive character management features

```
Add comprehensive character development and management tools:

1. Create character profile system with detailed attributes (appearance, personality, backstory)
2. Add character relationship mapping with relationship types and strength
3. Implement character consistency checker that flags inconsistencies
4. Add character appearance tracker showing where characters appear
5. Create character voice consistency analyzer
6. Add character development arc tracking
7. Implement character interview functionality for development
8. Create character casting feature (real people or fictional characters as inspiration)
9. Add character timeline showing development throughout the story
10. Implement character conflict tracking and resolution
```

## Prompt Set #5: Export Format Diversification

**Target Files:** `hearth.py`
**Objective:** Add additional export formats

```
Add additional export formats beyond Markdown and PDF:

1. Implement ePub export format for e-readers
2. Add DOCX export for Microsoft Word compatibility
3. Create HTML export with customizable templates
4. Add LaTeX export for academic writing
5. Implement plain text export with formatting stripped
6. Add screenplay format export
7. Create audiobook preparation with text segmentation
8. Add social media snippet exports (Twitter threads, LinkedIn articles)
9. Implement custom template system for personalized exports
10. Add export validation and quality checks
```

## Prompt Set #6: Advanced Text Editing Features

**Target Files:** `hearth.py`
**Objective:** Add sophisticated text editing capabilities

```
Add advanced text editing features to the writing interface:

1. Implement auto-completion for frequently used words and phrases
2. Add smart indentation that adapts to content type
3. Create code folding functionality for large documents
4. Add spell check integration with multiple language support
5. Implement grammar checking with style suggestions
6. Add thesaurus integration beyond the current basic functionality
7. Create find and replace with regex support
8. Add text transformation tools (uppercase, case conversion, etc.)
9. Implement outline view with collapsible sections
10. Add writing statistics and progress tracking
```

## Prompt Set #7: Research and Reference Tools

**Target Files:** `hearth.py`
**Objective:** Add research organization and reference features

```
Add research organization and reference management tools:

1. Create research note integration with tagging system
2. Add reference material linking to specific parts of the text
3. Implement fact-checking tools with source tracking
4. Add world-building tools with interconnected elements
5. Create timeline management for fictional events
6. Add research source organization with citation tools
7. Implement research-to-scene linking functionality
8. Create research note search and cross-reference system
9. Add image and media reference attachment
10. Implement research progress tracking and organization
```

## Prompt Set #8: Backup and Sync Features

**Target Files:** `hearth.py`
**Objective:** Add cloud backup and device sync

```
Add cloud backup and synchronization across devices:

1. Implement cloud storage integration (Dropbox, Google Drive, etc.)
2. Add automatic backup scheduling with customizable intervals
3. Create backup verification system to ensure integrity
4. Add version history and restore point management
5. Implement selective sync options (by project, file type, etc.)
6. Add encrypted backup options for sensitive content
7. Create backup status monitoring and notifications
8. Add offline mode with automatic sync when online
9. Implement backup sharing between user accounts
10. Add backup analytics showing storage usage and trends
```

## Prompt Set #9: Collaboration Features

**Target Files:** `hearth.py`
**Objective:** Add multi-user collaboration capabilities

```
Add multi-user collaboration features:

1. Implement version control integration (Git-based or custom)
2. Add real-time collaborative editing with conflict resolution
3. Create comment and review system for feedback
4. Add user permission management (view, edit, comment)
5. Implement change tracking with author attribution
6. Add collaborative writing sessions with presence indicators
7. Create collaborative outlining and planning tools
8. Add notification system for collaborators
9. Implement collaborative research and reference sharing
10. Add collaborative character and world-building tools
```

## Prompt Set #10: Analytics and Insights

**Target Files:** `hearth.py`
**Objective:** Add writing analytics and productivity insights

```
Add comprehensive writing analytics and productivity insights:

1. Implement daily/monthly word count tracking and trends
2. Add writing time analysis and productivity patterns
3. Create goal setting and achievement tracking system
4. Add writing streak and habit formation tools
5. Implement content analysis (dialogue vs narration, scene vs summary ratios)
6. Add readability analysis and complexity tracking
7. Create character balance analysis (screen time, dialogue distribution)
8. Add genre-specific analysis tools
9. Implement project completion forecasting
10. Add export functionality for analytics data and reports
```