# SameDaySuits Production System
# Setup Script - Creates complete production directory structure
# Run this script to set up the production environment

Write-Host "Setting up SameDaySuits Production System..." -ForegroundColor Green

# Create directory structure
$dirs = @(
    "production/src",
    "production/src/nesting",
    "production/src/core",
    "production/src/integrations", 
    "production/src/api",
    "production/docs",
    "production/tests",
    "production/config",
    "production/samples"
)

foreach ($dir in $dirs) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "Created: $dir" -ForegroundColor Gray
    }
}

# Core production files to copy
$coreFiles = @{
    # Core API
    "samedaysuits_api.py" = "production/src/core/"
    "production_pipeline.py" = "production/src/core/"
    "sds_cli.py" = "production/src/core/"
    
    # Nesting algorithms
    "master_nesting.py" = "production/src/nesting/"
    "hybrid_nesting.py" = "production/src/nesting/"
    "turbo_nesting.py" = "production/src/nesting/"
    "guillotine_nesting.py" = "production/src/nesting/"
    "skyline_nesting.py" = "production/src/nesting/"
    "shelf_nesting.py" = "production/src/nesting/"
    "improved_nesting.py" = "production/src/nesting/"
    "nesting_engine.py" = "production/src/nesting/"
    
    # Quality and monitoring
    "quality_control.py" = "production/src/core/"
    "production_monitor.py" = "production/src/core/"
    "cutter_queue.py" = "production/src/core/"
    
    # Integrations
    "database_integration.py" = "production/src/integrations/"
    "theblackbox_integration.py" = "production/src/integrations/"
    "pattern_scaler.py" = "production/src/core/"
    "graded_size_extractor.py" = "production/src/core/"
    
    # v6.4.3 Features
    "order_file_manager.py" = "production/src/core/"
    "order_continuity_validator.py" = "production/src/core/"
    "v6_4_3_integration.py" = "production/src/core/"
    
    # API and web
    "web_api.py" = "production/src/api/"
    "start_dashboard.py" = "production/src/api/"
}

Write-Host "`nCopying production files..." -ForegroundColor Yellow

foreach ($file in $coreFiles.Keys) {
    $source = $file
    $dest = $coreFiles[$file]
    
    if (Test-Path $source) {
        Copy-Item $source $dest -Force
        Write-Host "  Copied: $file -> $dest" -ForegroundColor Green
    } else {
        Write-Host "  Missing: $file" -ForegroundColor Red
    }
}

# Copy test files
$testFiles = @(
    "test_v6_4_3_end_to_end.py",
    "test_master_complete.py",
    "test_normal_man.py",
    "test_web_api.py"
)

Write-Host "`nCopying test files..." -ForegroundColor Yellow

foreach ($file in $testFiles) {
    if (Test-Path $file) {
        Copy-Item $file "production/tests/" -Force
        Write-Host "  Copied: $file" -ForegroundColor Green
    } else {
        Write-Host "  Missing: $file" -ForegroundColor Yellow
    }
}

# Copy documentation
$docFiles = @(
    "OPERATIONS_MANUAL_v6.4.2.md",
    "OPERATIONS_MANUAL_v6.4.3.md",
    "NESTING_ANALYSIS.md",
    "V6_4_3_TEST_SUMMARY.md"
)

Write-Host "`nCopying documentation..." -ForegroundColor Yellow

foreach ($file in $docFiles) {
    if (Test-Path $file) {
        Copy-Item $file "production/docs/" -Force
        Write-Host "  Copied: $file" -ForegroundColor Green
    }
}

# Copy sample data
$samples = @(
    "test_orders.json",
    "sample_scans"
)

Write-Host "`nCopying sample data..." -ForegroundColor Yellow

foreach ($item in $samples) {
    if (Test-Path $item) {
        Copy-Item $item "production/samples/" -Recurse -Force
        Write-Host "  Copied: $item" -ForegroundColor Green
    }
}

Write-Host "`nProduction setup complete!" -ForegroundColor Green
Write-Host "Directory structure:" -ForegroundColor Cyan
Write-Host "  production/"
Write-Host "    src/           - All source code"
Write-Host "    docs/          - Documentation"
Write-Host "    tests/         - Test scripts"
Write-Host "    config/        - Configuration files"
Write-Host "    samples/       - Sample data"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Review production/src/ for all working code"
Write-Host "  2. Check production/docs/ for documentation"
Write-Host "  3. Run tests: cd production && python -m pytest tests/"
Write-Host "  4. Start system: cd production/src/api && python web_api.py"
