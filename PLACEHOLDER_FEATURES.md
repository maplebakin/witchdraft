# WitchDraft Actual Features vs Placeholders

Based on code analysis, here's what's actually implemented versus what are truly placeholder features:

## FULLY IMPLEMENTED FEATURES

### Core Application Structure
- ✅ Complete Textual-based TUI application
- ✅ Single-file application structure (hearth.py)
- ✅ Command-line interface with argument parsing
- ✅ Configuration via constants at the top of the file
- ✅ SQLite database integration for entity storage
- ✅ File-based persistence (current_draft.md, compost.md)

### Writing Interface
- ✅ Basic text editing with TextArea widget
- ✅ Cursor pulsing animation (visual feedback)
- ✅ Focus mode (reduced UI chrome)
- ✅ Real-time draft saving to current_draft.md
- ✅ Echo panel for character information
- ✅ Ghost line for temporary notifications

### Entity Tracking (Shadow Bible)
- ✅ spaCy integration for named entity recognition
- ✅ Automatic extraction of PERSON and GPE entities
- ✅ SQLite database schema for entities, scenes, and traits
- ✅ Scene splitting based on headings
- ✅ Entity-to-scene relationship mapping
- ✅ Trait extraction for characters
- ✅ Background scanning thread
- ✅ Entity deduplication and normalization

### Visualization (Spiral Timeline)
- ✅ Canvas-based spiral visualization
- ✅ Scene-to-scene relationship mapping based on shared entities
- ✅ Interactive node dragging
- ✅ Edge drawing between related scenes
- ✅ Mouse event handling for interaction
- ✅ Dynamic layout based on scene position

### Data Management
- ✅ Soft deletion system (compost bin)
- ✅ Deletion tracking and restoration
- ✅ SQLite-based entity storage
- ✅ Scene position tracking
- ✅ Timestamp-based tracking

### CLI Commands
- ✅ Export functionality (Markdown and PDF)
- ✅ Constellation view (entity-to-scene mapping)
- ✅ Voice note ingestion
- ✅ Entry listing with filtering options
- ✅ Index building and maintenance

## PLACEHOLDER/UNIMPLEMENTED FEATURES

### Advanced NLP Features
- ❌ Custom entity types beyond PERSON/GPE
- ❌ Relationship extraction between entities
- ❌ Sentiment analysis for entities
- ❌ Named entity disambiguation
- ❌ Custom spaCy models for domain-specific entities

### UI/UX Enhancements
- ❌ Dark/light theme options
- ❌ Custom color schemes
- ❌ Advanced syntax highlighting
- ❌ Split-screen editing
- ❌ Rich text formatting
- ❌ Outline/structure view
- ❌ Advanced search and replace
- ❌ Word count and statistics

### Project Management
- ❌ Multi-project support
- ❌ Project templates
- ❌ Project import/export
- ❌ Project sharing features
- ❌ Version control integration

### Advanced Visualization
- ❌ Alternative graph layouts (force-directed, hierarchical)
- ❌ Entity relationship visualization
- ❌ Character arc visualization
- ❌ Timeline view (chronological vs spiral)
- ❌ Plot structure visualization
- ❌ Advanced filtering options for the timeline

### Character Development Tools
- ❌ Character profile management
- ❌ Character relationship mapping
- ❌ Character consistency checking
- ❌ Character appearance tracking
- ❌ Character voice consistency tools

### Plot Development Tools
- ❌ Plot structure templates
- ❌ Story arc visualization
- ❌ Conflict tracking
- ❌ Pacing analysis
- ❌ Chapter/scene goal tracking

### Research and Reference Tools
- ❌ Research note integration
- ❌ Reference material linking
- ❌ Fact-checking tools
- ❌ World-building tools
- ❌ Timeline management for fictional events

### Export and Publishing
- ❌ Multiple export formats (epub, mobi, html)
- ❌ Custom export templates
- ❌ Publishing workflow tools
- ❌ Manuscript formatting options
- ❌ Automated formatting for different publishers

### Collaboration Features
- ❌ Multi-user support
- ❌ Version control integration
- ❌ Comment and review system
- ❌ Change tracking
- ❌ Collaborative editing

### Backup and Sync
- ❌ Cloud backup options
- ❌ Sync across devices
- ❌ Automatic versioning
- ❌ Backup verification
- ❌ Restore point management

### Advanced Text Editing
- ❌ Auto-completion
- ❌ Smart indentation
- ❌ Code folding
- ❌ Spell check integration
- ❌ Grammar checking
- ❌ Thesaurus integration (beyond basic)

### Analytics and Insights
- ❌ Writing statistics and trends
- ❌ Productivity tracking
- ❌ Goal setting and achievement
- ❌ Writing streaks and habits
- ❌ Content analysis tools

## PRIORITY FOR IMPLEMENTATION

### High Priority
1. Multi-project support
2. Dark/light theme options
3. Advanced visualization options
4. Character development tools

### Medium Priority
1. Export format diversification
2. Advanced text editing features
3. Research and reference tools
4. Backup and sync features

### Low Priority
1. Collaboration features
2. Advanced NLP capabilities
3. Publishing workflow tools
4. Analytics and insights