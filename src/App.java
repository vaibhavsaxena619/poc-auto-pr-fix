import java.util.Arrays;
import java.util.List;

public class App {
    public static void main(String[] args) throws Exception {
        System.out.println("Hello, World!");
        System.out.println("Testing Jenkins PR automation!");
        List<String> sampleList = Arrays.asList("one", "two", "three");
        for (String item : sampleList) {
            System.out.println(item);
        }
    }
}