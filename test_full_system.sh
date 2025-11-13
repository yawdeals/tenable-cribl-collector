#!/bin/bash
echo "========================================="
echo "Full System Test"
echo "========================================="
echo ""

echo "1. Testing Python compatibility..."
python3 test_compatibility.py
TEST_RESULT=$?
echo ""

echo "2. Testing script compilation..."
python3 -m py_compile tenable_collector.py checkpoint_manager.py tenable_common.py
COMPILE_RESULT=$?
if [ $COMPILE_RESULT -eq 0 ]; then
    echo "✓ All scripts compiled successfully"
else
    echo "✗ Compilation failed"
fi
echo ""

echo "3. Testing collector script help..."
python3 tenable_collector.py --help > /dev/null 2>&1
HELP_RESULT=$?
if [ $HELP_RESULT -eq 0 ]; then
    echo "✓ Collector script help works"
else
    echo "✗ Collector script help failed"
fi
echo ""

echo "4. Testing wrapper script..."
./run_collector.sh --help > /dev/null 2>&1
WRAPPER_RESULT=$?
if [ $WRAPPER_RESULT -eq 0 ]; then
    echo "✓ Wrapper script works"
else
    echo "✗ Wrapper script failed"
fi
echo ""

echo "========================================="
echo "Test Summary"
echo "========================================="
if [ $TEST_RESULT -eq 0 ] && [ $COMPILE_RESULT -eq 0 ] && [ $HELP_RESULT -eq 0 ] && [ $WRAPPER_RESULT -eq 0 ]; then
    echo "✓ ALL TESTS PASSED"
    echo ""
    echo "Scripts are ready for production!"
    exit 0
else
    echo "✗ SOME TESTS FAILED"
    exit 1
fi
