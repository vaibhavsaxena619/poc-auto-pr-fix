import java.util.List;
import java.util.ArrayList;

public class App {
    // TEST CASE: Intentionally missing method for unfixable business logic test
    // This method is NOT implemented to verify that GPT creates a review PR
    // instead of either: (1) auto-implementing with guessed logic, or (2) deleting code
    
    public static void main(String[] args) throws Exception {
        System.out.println("Hello, World!");
        System.out.println("Testing Jenkins PR automation!");
        List<String> sampleList = List.of("one", "two", "three");
        for (String item : sampleList) {
            System.out.println(item);
        }
        
        // TEST 1 - Low confidence: Undefined variable (risky pattern)
        undefinedVariable = "This variable was never declared";
        System.out.println(undefinedVariable);
        
        // TEST 2 - Unfixable business logic: Missing applyDiscount implementation
        // This MUST trigger low confidence detection + review PR
        // Do NOT let GPT delete this code or auto-implement without review
        List<Double> prices = new ArrayList<>();
        prices.add(100.0);
        prices.add(250.0);
        prices.add(50.0);
        
        double total = 0;
        for (Double price : prices) {
            total += applyDiscount(price);  // ERROR: Missing method - requires domain knowledge
        }
        System.out.println("Total with discount: " + total);
    }
    
    // INTENTIONALLY NOT IMPLEMENTED
    // This method requires business requirements to implement:
    // - What discount percentage/fixed amount?
    // - Does it depend on price ranges?
    // - Are there customer segments?
    // - Product category exceptions?
    // - Conflict with existing promotions?
    // If GPT auto-implements without these details, it adds UNREVIEWED business logic
}
