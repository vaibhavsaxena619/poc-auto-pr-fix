import java.util.List;
import java.util.ArrayList;
import com.fasterxml.jackson.databind.ObjectMapper;

public class App {
    public static void main(String[] args) throws Exception {
        System.out.println("Hello, World!");
        System.out.println("Testing Jenkins PR automation!");
        testMissingImport();
        testFormatting();
        testLintIssue();
        testAssertionError();
    }
    
    public void run() {
        List<String> users = new ArrayList<>();
        users.add("test-user");
        System.out.println("Users: " + users);
    }
    
    // Issue 1: missing_import - undefined class without import
    public static void testMissingImport() {
        ObjectMapper mapper = new ObjectMapper();
        System.out.println("Mapper: " + mapper);
    }
    
    // Issue 2: formatting - invalid syntax
    public static void testFormatting() {
        System.out.println("Syntax error - missing closing brace");
    }
    
    // Issue 3: lint_issue - unused variable
    public static void testLintIssue() {
        String unusedVariable = "This is never used";
        int deadCodeVar = 42;
        System.out.println("Only printing this");
    }
    
    // Issue 4: test_failure - assertion error
    public static void testAssertionError() {
        assert false : "This assertion will fail during testing";
    }
}