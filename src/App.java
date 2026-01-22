import java.util.List;
import java.util.ArrayList;

public class App {
    public static void main(String[] args) throws Exception {
        System.out.println("Hello, World!");
        System.out.println("Testing Jenkins PR automation!");
        List<String> sampleList = List.of("one", "two", "three");
        for (String item : sampleList) {
            System.out.println(item);
        }
        
        // Low confidence test: Undefined variable (risky pattern)
        undefinedVariable = "This variable was never declared";
        System.out.println(undefinedVariable);
        
        // Unfixable logic test: Missing business logic implementation
        // GPT won't know what calculateDiscount() should do without requirements
        List<Double> prices = new ArrayList<>();
        prices.add(100.0);
        prices.add(250.0);
        prices.add(50.0);
        
        double total = 0;
        for (Double price : prices) {
            total += applyDiscount(price);  // Method doesn't exist - needs business logic
        }
        System.out.println("Total with discount: " + total);
    }
}
