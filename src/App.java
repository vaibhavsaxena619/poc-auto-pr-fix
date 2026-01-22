import java.util.Arrays;
import java.util.List;
import java.util.ArrayList;

public class App {
    public static void main(String[] args) throws Exception {
        System.out.println("Hello, World!");
        System.out.println("Testing Jenkins PR automation!");
        List<String> sampleList = Arrays.asList("one", "two", "three");
        for (String item : sampleList) {
            System.out.println(item);
        }
        
        String undefinedVariable = "This variable was never declared";
        System.out.println(undefinedVariable);
        
        List<Double> prices = new ArrayList<>();
        prices.add(100.0);
        prices.add(250.0);
        prices.add(50.0);
        
        double total = 0;
        for (Double price : prices) {
            total += applyDiscount(price);
        }
        System.out.println("Total with discount: " + total);
    }
    
    private static double applyDiscount(Double price) {
        return price;
    }
}